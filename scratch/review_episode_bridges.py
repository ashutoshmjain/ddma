import os
import sys
import json
import time
import urllib.request
import urllib.error

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

def load_settings():
    settings_path = "settings.json"
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def call_gemini_api_direct(prompt, api_key, model_name="gemini-2.0-flash"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json"
        }
    }
    
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text_out = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_out)
    except urllib.error.HTTPError as he:
        if he.code == 429:
            print(f"Direct REST model {model_name} rate limited (429), waiting 8s...", file=sys.stderr)
            time.sleep(8)
        else:
            print(f"Direct REST model {model_name} HTTP Error {he.code}: {he.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Direct REST model {model_name} error: {e}", file=sys.stderr)
        return None

def call_gemini(prompt, api_key):
    model_names = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-pro-latest"]
    
    # Try Google GenAI SDK first if available
    if HAS_GENAI:
        creds_path = "gemini-creds.json"
        configured = False
        if os.path.exists(creds_path):
            try:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(creds_path)
                genai.configure(credentials=creds)
                configured = True
            except Exception:
                pass
        if not configured and api_key:
            try:
                genai.configure(api_key=api_key)
                configured = True
            except Exception:
                pass
                
        if configured:
            for model_name in model_names:
                try:
                    print(f"Attempting bridge review with GenAI SDK model {model_name}...")
                    model = genai.GenerativeModel(model_name)
                    res = model.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    if res and res.text:
                        return json.loads(res.text)
                except Exception as e:
                    err_str = str(e)
                    print(f"GenAI SDK model {model_name} failed: {err_str}", file=sys.stderr)
                    if "429" in err_str or "quota" in err_str.lower():
                        print("Rate limited, sleeping 7 seconds...", file=sys.stderr)
                        time.sleep(7)

    # Fallback to direct REST API
    for model_name in model_names:
        print(f"Attempting bridge review with direct REST API model {model_name}...")
        res = call_gemini_api_direct(prompt, api_key, model_name=model_name)
        if res:
            return res
            
    return None

def review_episode_bridges(plan_path):
    if not os.path.exists(plan_path):
        print(f"Error: {plan_path} not found.", file=sys.stderr)
        return False

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    # Filter active locked clips sorted by num
    locked_clips = [c for c in plan_data if c.get("locked", False) and not c.get("hidden", False)]
    locked_clips.sort(key=lambda x: x["num"])

    if len(locked_clips) < 2:
        print("Not enough locked clips to review bridge transitions.", file=sys.stderr)
        return False

    # Extract Gemini API Key
    settings = load_settings()
    api_key = settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")

    # Build context prompt listing all clips in sequence
    prompt_lines = [
        "You are an expert podcast producer and narrative editor for DeepDive Media Automator (DDMA).",
        "Your task is to review and generate curiosity-provoking bridge question cards for transitions between podcast clips.",
        "A bridge card appears AT THE END of Clip N, right before Clip N+1 begins.",
        "CRITICAL RULE: The bridge question card MUST pose a bold, intriguing question that specifically previews the concept, metaphor, paradox, or central thesis of the UPCOMING Clip N+1.",
        "",
        "Here is the complete sequence of locked clips for this episode in chronological order:",
        ""
    ]

    for i, clip in enumerate(locked_clips):
        # Gather text snippet from segments
        texts = [s.get("text", "") for s in clip.get("segments", []) if s.get("type") == "audio"]
        full_text = " ".join(texts)
        if len(full_text) > 400:
            snippet = full_text[:250] + " ... " + full_text[-150:]
        else:
            snippet = full_text

        curr_bridge = clip.get("bridge_text", [])
        if isinstance(curr_bridge, list):
            curr_bridge_str = " ".join(curr_bridge)
        else:
            curr_bridge_str = str(curr_bridge)

        prompt_lines.append(f"Clip {clip['num']} (Title: '{clip.get('title')}')")
        prompt_lines.append(f"  Summary/Transcript: {snippet}")
        prompt_lines.append(f"  Current Bridge Card Question: '{curr_bridge_str}'")
        prompt_lines.append("")

    prompt_lines.extend([
        "INSTRUCTIONS:",
        "1. For each Clip N (except the last clip of the episode), evaluate the transition into Clip N+1.",
        "2. Ensure the bridge question for Clip N directly teasers the main paradox, question, or story in Clip N+1.",
        "3. Keep each question punchy, thought-provoking, and written in Segoe UI Bold standard (10 to 20 words).",
        "4. Return a JSON array of objects, one for each clip, in the following exact format:",
        "[",
        '  {"num": 1, "bridge_text": ["Curiosity question for transition into Clip 2?"]},',
        '  {"num": 2, "bridge_text": ["Curiosity question for transition into Clip 3?"]}',
        "]",
        "Note: The last clip of the episode should have an empty or closing bridge_text list, e.g. []."
    ])

    prompt = "\n".join(prompt_lines)

    result = call_gemini(prompt, api_key)
    if not result or not isinstance(result, list):
        print("Error: Invalid response format from Gemini.", file=sys.stderr)
        return False

    # Map results back to plan_data
    updated_count = 0
    result_dict = {item.get("num"): item.get("bridge_text") for item in result if isinstance(item, dict) and "num" in item}

    for clip in plan_data:
        c_num = clip["num"]
        if c_num in result_dict:
            new_bt = result_dict[c_num]
            if isinstance(new_bt, str):
                new_bt = [new_bt]
            if new_bt is not None:
                clip["bridge_text"] = new_bt
                updated_count += 1
                print(f"Updated Clip {c_num} bridge_text: {new_bt}")

    # Write back to plan.json
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=4)

    print(f"\nSuccessfully reviewed and updated bridge cards for {updated_count} clips in {plan_path}!")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Review and refine episode bridge cards using Gemini.")
    parser.add_argument("--plan-file", type=str, default="plan.json", help="Path to plan JSON file")
    args = parser.parse_args()

    success = review_episode_bridges(args.plan_file)
    sys.exit(0 if success else 1)
