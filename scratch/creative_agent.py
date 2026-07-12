#!/usr/bin/env python3
import os
import sys
import json
import argparse
import shutil
import subprocess
import time
from datetime import datetime

# Initialize the Gemini API client
try:
    import google.generativeai as genai
except ImportError:
    print("Error: 'google-generativeai' package is not installed. Please install it first.")
    sys.exit(1)

PYTHON_EXE = r"C:\Users\ashut\AppData\Local\Programs\Python\Python312\python.exe"

def parse_args():
    parser = argparse.ArgumentParser(description="DDMA Autonomous Creative Curation Agent")
    parser.add_argument("--project", required=True, help="Name/ID of the project folder (e.g. episode_245)")
    parser.add_argument("--audio", help="Path to raw source audio file to initialize the project with")
    parser.add_argument("--model", default="gemini-1.5-pro", help="Gemini model to use for planning")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 1. Verify Gemini API Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set. Please set it before running.")
        sys.exit(1)
    
    genai.configure(api_key=api_key)
    
    # 2. Setup Project Directory
    project_dir = os.path.join("projects", args.project)
    os.makedirs(project_dir, exist_ok=True)
    print(f"[*] Project directory initialized at: {project_dir}")
    
    # Check for audio file
    audio_file_in_project = None
    # Look for existing audio files in project
    for f in os.listdir(project_dir):
        if f.lower().endswith(('.mp3', '.m4a', '.wav', '.mp4')):
            audio_file_in_project = f
            break
            
    if args.audio:
        if not os.path.exists(args.audio):
            print(f"Error: Source audio file '{args.audio}' not found.")
            sys.exit(1)
        ext = os.path.splitext(args.audio)[1]
        target_name = f"audio{ext}"
        target_path = os.path.join(project_dir, target_name)
        print(f"[*] Copying source audio '{args.audio}' to '{target_path}'...")
        shutil.copy2(args.audio, target_path)
        audio_file_in_project = target_name
    
    if not audio_file_in_project:
        print("Error: No audio file found in project and no --audio argument provided.")
        sys.exit(1)
        
    audio_path = os.path.join(project_dir, audio_file_in_project)
    
    # Write project_info.json if missing
    info_path = os.path.join(project_dir, "project_info.json")
    if not os.path.exists(info_path):
        info_data = {
            "id": args.project,
            "name": args.project.replace("_", " ").title(),
            "created_at": datetime.now().isoformat()
        }
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info_data, f, indent=4)
        print(f"[*] Created project_info.json")

    # 3. Perform Whisper Transcription if missing
    trans_path = os.path.join(project_dir, "transcription.json")
    if not os.path.exists(trans_path):
        print(f"[*] transcription.json missing. Running Whisper transcription...")
        cmd = [
            PYTHON_EXE,
            "ddma.py",
            "transcribe",
            "--audio",
            audio_path,
            "--out",
            trans_path
        ]
        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            print("Error: Whisper transcription failed.")
            sys.exit(1)
    else:
        print(f"[*] Found existing transcription.json at {trans_path}")
        
    # 4. Load Transcription Data
    with open(trans_path, "r", encoding="utf-8") as f:
        trans_data = json.load(f)
        
    segments = trans_data.get("segments", [])
    if not segments:
        print("Error: No segments found in transcription.json.")
        sys.exit(1)
        
    print(f"[*] Loaded {len(segments)} transcript segments. Preparing summary for LLM...")
    
    # Simplify segment structure to fit model token limits safely
    simplified_segments = []
    for s in segments:
        simplified_segments.append({
            "start": round(s.get("start", 0), 2),
            "end": round(s.get("end", 0), 2),
            "text": s.get("text", "").strip()
        })
        
    # 5. Load Available Music Stings
    music_dir = "music"
    music_files = []
    if os.path.exists(music_dir):
        music_files = [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav'))]
    print(f"[*] Found {len(music_files)} available music stings in {music_dir}/")

    # 6. Formulate Gemini prompt using the Creative Process guidelines
    prompt = f"""You are the Creative Director Agent for the DeepDive Media Automator (DDMA).
Your task is to analyze the simplified transcript segments of a podcast episode and generate a highly engaging, professional multi-clip plan.json.

### Creative Guidelines & Strategies:
1. **Thematic Clips**:
   - Divide the entire timeline into 5 to 10 distinct, thematic clips.
   - Each clip must have a clear beginning (hook), middle, and end.
   - The total duration of any single clip card MUST remain strictly under 2 minutes and 55 seconds (175 seconds) to fit social media posting limits.
   - Note: The total duration is calculated as: `Total = Sum(segment_durations) - Sum(segment_crossfades)`.

2. **Narrative Anchoring (Repeated Core Theme / Punchline)**:
   - Identify a highly punchy, 10-to-15-second speech block (the "theme core" or "punchline") in the transcript that summarizes the central thesis or key hook.
   - Re-use/repeat this exact speech segment across multiple clips (e.g., at the end of Clip 1, and repeated as the starting segment of Clip 5) to anchor the narrative chorus.
   - Identify which segment you chose, and duplicate it exactly (the same start and end timestamps) in those clips.

3. **Host Welcome Hook Transition**:
   - Look for the introduction or announcement segment in the first 2-3 minutes of the transcript where the hosts welcome the audience or introduce the show.
   - Place the "deepDive-strong.mp3" music sting (duration: 13.0s, crossfade: 0.3s, volume: 1.0) immediately after this welcome speech segment, typically in Clip 2, to ground the show format early.

4. **Music Stings & Transition Overlaps**:
   - Intersperse short transition stings (from the available music list below) between speech blocks.
   - Set duration to 4.5s for normal stings, volume to 1.0 (or 0.75 for soft backing stings), and crossfade to 0.3s (up to 5.0s for deep blends).
   - Use crossfades (`crossfade > 0.0`) to overlap segment boundaries, hiding silent gaps and clicks.

5. **Curiosity-Provoking Question (Bridge Text)**:
   - Provide a list containing 1 bold, curiosity-provoking question for the "bridge_text" field in each clip to transition between slides.

### Available Music Stings:
{json.dumps(music_files, indent=2)}

### Simplified Transcript Segments:
{json.dumps(simplified_segments, indent=2)}

### Output Format:
You MUST respond with a JSON array matching the plan.json schema exactly. Do not include markdown code block formatting or explanations outside the JSON array:
[
  {{
    "num": 1,
    "title": "Clip Title Here",
    "bridge_text": [
      "Curiosity-provoking question?"
    ],
    "segments": [
      {{
        "type": "audio",
        "start": 0.0,
        "end": 45.5,
        "duration": 45.5,
        "text": "Exact text matching transcription segments"
      }},
      {{
        "type": "music",
        "music_file": "Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3",
        "duration": 4.5,
        "crossfade": 0.3,
        "volume": 1.0
      }}
    ],
    "locked": true
  }}
]
"""

    print(f"[*] Calling Gemini API ({args.model}) for creative planning...")
    start_api_time = time.time()
    
    model = genai.GenerativeModel(args.model)
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    print(f"[*] Gemini API responded in {time.time() - start_api_time:.2f} seconds.")
    
    try:
        plan_data = json.loads(response.text)
    except json.JSONDecodeError as e:
        print("Error: Gemini returned invalid JSON:")
        print(response.text)
        sys.exit(1)
        
    # Write to projects/{project}/plan.json
    plan_path = os.path.join(project_dir, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=4)
        
    # Copy to root plan.json
    shutil.copy2(plan_path, "plan.json")
    
    print(f"[+] Autonomous creative planning complete!")
    print(f"[+] Plan saved to: {plan_path}")
    print(f"[+] Configured clips count: {len(plan_data)}")
    print(f"[+] You can now launch the DDMA Curator Server and open http://localhost:8000/curator.html to preview and tweak!")

if __name__ == "__main__":
    main()
