import typer
try:
    import whisper
except ImportError:
    whisper = None
import json
import os
import re
import subprocess
import time
import shutil
from typing import Optional

app = typer.Typer(help="DeepDive Media Automator (DDMA) CLI Tool")


def resolve_acoustic_word_end(raw_end: float, next_word_start: Optional[float] = None, audio_path: Optional[str] = None) -> float:
    """
    Extends a Whisper word end timestamp into the natural breath pause so trailing sibilants/plosives
    (e.g., "-es" in "senses") are never clipped in half.
    Uses an 180ms sibilant safety cushion clamped 40ms before next_word_start, refined by 16kHz PCM RMS energy if audio_path is available.
    """
    max_extend = min(0.32, max(0.0, (next_word_start - raw_end) - 0.04)) if next_word_start is not None else 0.22
    if max_extend <= 0.02:
        return round(raw_end, 2)
    default_ext = round(raw_end + min(0.18, max_extend), 2)
    if not audio_path or not os.path.exists(audio_path):
        return default_ext
    try:
        import numpy as np
        win_start = max(0.0, raw_end - 0.05)
        win_dur = 0.05 + max_extend
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{win_start:.3f}", "-t", f"{win_dur:.3f}", "-i", audio_path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        arr = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        if len(arr) < 160:
            return default_ext
        last_active_t = raw_end + min(0.12, max_extend)
        for i in range(800, len(arr) - 160, 160):
            rms = float(np.sqrt(np.mean(arr[i:i + 160] ** 2)))
            t_frame = win_start + (i + 160) / 16000.0
            if rms > 0.0020:
                last_active_t = t_frame + 0.03
        return round(min(raw_end + max_extend, max(raw_end + min(0.12, max_extend), last_active_t)), 2)
    except Exception:
        return default_ext


def parse_spoken_cue_tripartite_plan(t_data: dict, default_visual_source: str = "mosaic", audio_path: Optional[str] = None) -> list:
    """
    Deterministically detects spoken NotebookLM clip cues ('Clip 1', 'Clip one', etc.)
    and snaps tripartite boundaries:
    - Clip 0 (Show Prologue / Ep Intro)
    - Clips 1..N with Punchline Hook, Mid-Sting, Core Deliberation, Outro Teaser, Outro-Sting.
    """
    segments = t_data.get("segments", [])
    if not segments:
        return []

    all_words = []
    for s in segments:
        all_words.extend(s.get("words", []))
    if not all_words:
        return []

    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
        "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20
    }

    raw_cues = []
    for i, s in enumerate(segments):
        t = s.get("text", "")
        m = re.search(r"\bclip\s+(\w+)\b", t, re.IGNORECASE)
        if m and "next clip" not in t.lower() and "final clip" not in t.lower():
            w_val = m.group(1).lower()
            c_num = int(w_val) if w_val.isdigit() else word_to_num.get(w_val)
            if c_num is not None:
                w_start = s["start"]
                for w in s.get("words", []):
                    if "clip" in w.get("word", "").lower():
                        w_start = w["start"]
                        break
                intro_start = s["start"] if (s["start"] < w_start and (w_start - s["start"]) < 4.0) else w_start
                raw_cues.append({"num": c_num, "seg_idx": i, "start": intro_start, "seg": s})

    if len(raw_cues) < 3:
        return []

    raw_cues.sort(key=lambda x: x["start"])
    cues = []
    seen_nums = set()
    for rc in raw_cues:
        if rc["num"] not in seen_nums:
            cues.append(rc)
            seen_nums.add(rc["num"])

    total_audio_dur = all_words[-1]["end"]

    def get_words_between(st, et):
        return [w for w in all_words if w["start"] >= st - 0.05 and w["end"] <= et + 0.05]

    def get_text_between(st, et):
        w_list = get_words_between(st, et)
        return " ".join(w["word"].strip() for w in w_list).strip()

    clips = []
    first_cue_start = cues[0]["start"]

    # Clip 0: Prologue (if there is content before first clip cue)
    if first_cue_start > 20.0:
        w_prev_c0 = [w for w in all_words if w["start"] < first_cue_start - 0.02]
        raw_c0_end = round(w_prev_c0[-1]["end"], 2) if w_prev_c0 else round(first_cue_start, 2)
        c0_end = resolve_acoustic_word_end(raw_c0_end, first_cue_start, audio_path)
        c0_words = get_words_between(0.0, raw_c0_end)
        raw_c0_hook_end = min(20.0, raw_c0_end)
        for w in c0_words:
            if 12.0 <= w["end"] <= 28.0 and any(w.get("word", "").strip().endswith(p) for p in [".", "?", "!"]):
                raw_c0_hook_end = round(w["end"], 2)
                break
        delib_start = raw_c0_hook_end + 0.3
        for w in c0_words:
            if w["start"] > raw_c0_hook_end + 0.01:
                delib_start = w["start"]
                break
        c0_hook_end = resolve_acoustic_word_end(raw_c0_hook_end, delib_start, audio_path)
        c0_hook_text = get_text_between(0.0, raw_c0_hook_end)
        c0_body_text = get_text_between(delib_start, raw_c0_end)
        clips.append({
            "num": 0,
            "title": "What Exactly Is Reality?",
            "start": 0.0,
            "end": c0_end,
            "duration": c0_end,
            "bridge_text": [f"What Is Clip {cues[0]['num']} ?"],
            "segments": [
                {"type": "audio", "start": 0.0, "end": c0_hook_end, "duration": c0_hook_end, "text": c0_hook_text},
                {"type": "music", "start": None, "end": None, "duration": 5.5, "silence_before": 0.2, "gap": 0.2, "fade_out": 2.0, "crossfade": 1.0, "music_file": "music/Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3"},
                {"type": "audio", "start": round(delib_start, 2), "end": c0_end, "duration": round(c0_end - delib_start, 2), "text": c0_body_text},
                {"type": "music", "start": None, "end": None, "duration": 5.5, "silence_before": 0.2, "gap": 0.2, "fade_out": 2.0, "crossfade": 0.0, "music_file": "music/deepDive-conclusion.mp3"}
            ],
            "locked": False,
            "visual_source": default_visual_source
        })

    for idx, cue in enumerate(cues):
        c_num = cue["num"]
        st = round(cue["start"], 2)
        if idx + 1 < len(cues):
            next_st = cues[idx + 1]["start"]
            # Use strict '< next_st - 0.02' so zero-duration words ('Clip' at next_st) are never included in previous clip
            w_prev = [w for w in all_words if w["start"] < next_st - 0.02]
            raw_et = round(w_prev[-1]["end"], 2) if w_prev else round(next_st, 2)
            et = resolve_acoustic_word_end(raw_et, next_st, audio_path)
        else:
            raw_et = round(total_audio_dur, 2)
            et = raw_et

        clip_words = get_words_between(st, raw_et)
        if not clip_words:
            continue

        raw_h_end = None
        for w in clip_words:
            w_dur = w["end"] - st
            w_txt = w.get("word", "").strip()
            if w_dur >= 7.0 and any(w_txt.endswith(p) for p in [".", "?", "!"]):
                raw_h_end = round(w["end"], 2)
                break
        if not raw_h_end:
            raw_h_end = round(min(raw_et, st + 15.0), 2)

        next_words = [w for w in clip_words if w["start"] > raw_h_end + 0.01]
        delib_start = next_words[0]["start"] if next_words else raw_h_end + 0.3
        h_end = resolve_acoustic_word_end(raw_h_end, delib_start, audio_path)

        hook_text = get_text_between(st, raw_h_end)
        body_text = get_text_between(delib_start, raw_et)

        title = f"Part {c_num}"
        m_title = re.search(r"clip\s+\w+[\s,.:\-]+([^.!?\n]+)", hook_text, re.IGNORECASE)
        if m_title:
            cand = m_title.group(1).strip()
            cand = re.sub(r"\s*-\s*", "-", cand)
            cand = re.sub(r"^(?:the|a|an)\s+", "", cand, flags=re.IGNORECASE)
            cand_words = cand.split()
            if 1 <= len(cand_words) <= 3:
                title = cand.title()
            elif len(cand_words) > 3:
                title = " ".join(cand_words[:3]).title()

        bridge_q = f"What Is Part {c_num + 1} ?"
        if idx + 1 < len(cues):
            next_hook = get_text_between(cues[idx + 1]["start"], min(total_audio_dur, cues[idx + 1]["start"] + 15.0))
            m_next_t = re.search(r"clip\s+\w+[\s,.:\-]+([^.!?\n]+)", next_hook, re.IGNORECASE)
            if m_next_t:
                nt = re.sub(r"^(?:the|a|an)\s+", "", m_next_t.group(1).strip(), flags=re.IGNORECASE)
                nt_words = nt.split()[:3]
                if nt_words:
                    bridge_q = f"What Is {' '.join(nt_words).title()} !"

        sting_file = "music/Howling (Sting) - Gunnar Olsen.mp3" if c_num % 2 == 1 else "music/Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3"

        clips.append({
            "num": c_num,
            "title": title,
            "start": st,
            "end": et,
            "duration": round(et - st, 2),
            "bridge_text": [bridge_q],
            "segments": [
                {"type": "audio", "start": st, "end": h_end, "duration": round(h_end - st, 2), "text": hook_text},
                {"type": "music", "start": None, "end": None, "duration": 5.5, "silence_before": 0.2, "gap": 0.2, "fade_out": 2.0, "crossfade": 1.0, "music_file": sting_file},
                {"type": "audio", "start": round(delib_start, 2), "end": et, "duration": round(et - delib_start, 2), "text": body_text},
                {"type": "music", "start": None, "end": None, "duration": 5.5, "silence_before": 0.2, "gap": 0.2, "fade_out": 2.0, "crossfade": 0.0, "music_file": "music/deepDive-conclusion.mp3"}
            ],
            "locked": False,
            "visual_source": default_visual_source
        })

    return clips


def cast_tripartite_plan_with_gemini(t_data: dict, num_clips: Optional[int] = None, api_key: Optional[str] = None, default_visual_source: str = "mosaic", audio_path: Optional[str] = None) -> list:
    """
    Parses a NotebookLM tripartite podcast transcript where each clip consists of:
    1. Punchline Hook (10-20s): Spoken thesis statement, announcing clip number and/or title.
    2. Core Deliberation (~2 mins): In-depth discussion between Satosha and Satoshi.
    3. Outro Teaser (10-20s): Spoken bridge stating what to look for in the next clip.

    First checks for deterministic spoken clip cues ('Clip 1', 'Clip one', etc.) with microsecond snapping.
    Otherwise prompts Gemini to identify every clip boundary.
    """
    spoken_clips = parse_spoken_cue_tripartite_plan(t_data, default_visual_source=default_visual_source, audio_path=audio_path)
    if spoken_clips:
        typer.echo(f"[Spoken Cue Caster] Detected {len(spoken_clips)} spoken tripartite clip cues with exact boundary snapping!")
        return spoken_clips

    words = []
    for s in t_data.get("segments", []):
        words.extend(s.get("words", []))
    if not words:
        return []

    total_dur = words[-1]["end"]
    if not num_clips:
        num_clips = max(1, int(round(total_dur / 150.0)))

    # Resolve Gemini API Key
    if not api_key:
        api_key = get_gemini_api_key() if "get_gemini_api_key" in globals() else None
    if not api_key:
        sett_file = os.path.join(os.path.dirname(__file__), "settings.json")
        if os.path.exists(sett_file):
            try:
                with open(sett_file, "r", encoding="utf-8") as sf:
                    api_key = json.load(sf).get("gemini_api_key")
            except Exception:
                pass
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")

    # Build timed sample of transcript for Gemini
    sample_lines = []
    for seg in t_data.get("segments", []):
        st = seg.get("start", 0.0)
        et = seg.get("end", 0.0)
        txt = seg.get("text", "").strip()
        sample_lines.append(f"[{st:.1f}s - {et:.1f}s] {txt}")

    transcript_sample = "\n".join(sample_lines[:120]) + "\n...\n" + "\n".join(sample_lines[-60:]) if len(sample_lines) > 180 else "\n".join(sample_lines)

    prompt = f"""You are the Executive Producer for the "Deep Dive with Gemini" podcast pipeline.
The provided episode transcript is generated using NotebookLM's structured tripartite pattern:
Every clip consists of 3 distinct spoken parts:
1. Punchline Hook (10–20s): Spoken thesis statement, announcing the clip number and title.
2. Core Deliberation (~2 mins): In-depth conversational discussion between Satosha and Satoshi.
3. Outro Teaser (10–20s): Spoken bridge stating what to look for in the next clip.

Episode Transcript Sample:
{transcript_sample}

Task:
Analyze the transcript and identify all tripartite clips (target approximately {num_clips} clips).
- Number clips starting at 0 (`num: 0`) for the Episode Prologue / Cold Open (before the hosts announce "Clip 1"), then `num: 1` for spoken "Clip 1", `num: 2` for spoken "Clip 2", etc., so clip numbers strictly mirror the spoken word!
For each clip, return a JSON object with:
- "num": integer (0, 1, 2, 3...)
- "title":
  * For Clip 0 (`num == 0`): The overarching Episode Title (3-5 words, e.g. "What Exactly Is Reality?").
  * For Clip 1+ (`num >= 1`): STRICTLY MAXIMUM 3 WORDS designed to capture attention — typically the scientific concept, scientist name, or core idea (e.g. "8D Totality", "Sensory Split", "Division Algebras", "Quaternions"). Drop leading articles like "The" if needed to stay ≤ 3 words.
- "hook_quote": Exact spoken opening thesis statement (1-2 sentences, 10-20s)
- "punchline_start_phrase": First 3-5 words spoken in the punchline hook
- "punchline_end_phrase": Last 3-5 words of the punchline hook before deliberation
- "deliberation_start_phrase": First 3-5 words of the core deliberation
- "deliberation_end_phrase": Last 3-5 words of the core deliberation before teaser
- "teaser_start_phrase": First 3-5 words of the outro teaser (e.g. "In the next clip", "Coming up next")
- "teaser_end_phrase": Last 3-5 words of the outro teaser
- "coming_up_title": Short title (≤ 3 words) of the next clip teased in the outro teaser
- "bridge_question": STRICTLY MAXIMUM 5 WORDS punchy curiosity question/exclamation for the outro card (e.g. "What is 8D Totality !", "Why Four Division Algebras ?"). NEVER write "Coming up in Clip..." or long story sentences because the hosts already speak that aloud!
- "visual_source": "{default_visual_source}"

Return ONLY a JSON array of objects without Markdown formatting."""

    parsed_clips = []
    if api_key and not api_key.startswith("AQ."):
        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        for m in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        parsed_clips = parsed
                        typer.echo(f"[Gemini Caster] Successfully cast {len(parsed_clips)} tripartite clips with {m}!")
                        break
            except Exception as ge:
                typer.echo(f"[Gemini Caster] [{m}] Notice: {ge}")

    # Fallback heuristic if API call failed
    if not parsed_clips:
        typer.echo("[Tripartite Caster] Utilizing deterministic sentence snapping fallback...")
        target_clip_dur = total_dur / max(1, num_clips)
        curr_s = 0.0
        for i in range(num_clips):
            c_num = i + 1
            curr_e = min(total_dur, curr_s + target_clip_dur)
            c_obj = build_rough_cut_segments(c_num, curr_s, curr_e, t_data.get("segments", []), num_clips)
            c_obj["visual_source"] = default_visual_source
            parsed_clips.append(c_obj)
            curr_s = curr_e
        return parsed_clips

    # Snap phrase boundaries to Whisper word-level timestamps
    final_clips = []
    cursor_time = 0.0

    for idx, c in enumerate(parsed_clips):
        c_num = c.get("num", idx + 1)
        title = c.get("title", f"Part {c_num}")
        hook_quote = c.get("hook_quote", "")
        p_start_p = c.get("punchline_start_phrase", "")
        p_end_p = c.get("punchline_end_phrase", "")
        d_start_p = c.get("deliberation_start_phrase", "")
        d_end_p = c.get("deliberation_end_phrase", "")
        t_start_p = c.get("teaser_start_phrase", "")
        t_end_p = c.get("teaser_end_phrase", "")

        # 1. Snap Punchline Hook (10-20s)
        h_start, _ = snap_quote_to_words(p_start_p, words, search_start_sec=cursor_time)
        if h_start is None:
            h_start = cursor_time
        _, raw_h_end = snap_quote_to_words(p_end_p, words, search_start_sec=h_start + 8.0)
        if raw_h_end is None or raw_h_end <= h_start:
            raw_h_end = round(min(total_dur, h_start + 18.0), 2)

        # 2. Mid Sting (Bluesy Vibes or Howling)
        mid_music = "Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3" if c_num % 2 == 1 else "Howling (Sting) - Gunnar Olsen.mp3"

        # 3. Snap Deliberation + Spoken Outro Teaser (single continuous body audio segment)
        d_start, _ = snap_quote_to_words(d_start_p, words, search_start_sec=raw_h_end)
        if d_start is None:
            d_start = round(raw_h_end + 0.3, 2)
        h_end = resolve_acoustic_word_end(raw_h_end, d_start, audio_path)

        _, raw_t_end = snap_quote_to_words(t_end_p, words, search_start_sec=d_start + 60.0)
        if raw_t_end is None or raw_t_end <= d_start:
            _, raw_t_end = snap_quote_to_words(d_end_p, words, search_start_sec=d_start + 60.0)
        if raw_t_end is None or raw_t_end <= d_start:
            raw_t_end = round(min(total_dur, d_start + 115.0), 2)

        next_ws = [w["start"] for w in words if w["start"] > raw_t_end + 0.01]
        next_w_start = next_ws[0] if next_ws else raw_t_end + 0.5
        t_end = resolve_acoustic_word_end(raw_t_end, next_w_start, audio_path)

        # Build canonical 4-element segments list: Hook -> Mid-Sting -> Deliberation+Teaser -> Outro-Sting
        segs = [
            {
                "type": "audio",
                "start": h_start,
                "end": h_end,
                "duration": round(h_end - h_start, 2),
                "text": hook_quote
            },
            {
                "type": "music",
                "music_file": mid_music,
                "duration": 5.5,
                "silence_before": 0.2,
                "gap": 0.2,
                "fade_out": 2.0,
                "crossfade": 1.0,
                "volume": 1.0
            },
            {
                "type": "audio",
                "start": d_start,
                "end": t_end,
                "duration": round(t_end - d_start, 2),
                "text": f"Deliberation & Teaser: {title}"
            },
            {
                "type": "music",
                "music_file": "deepDive-conclusion.mp3",
                "duration": 5.5,
                "silence_before": 0.2,
                "gap": 0.2,
                "fade_out": 2.0,
                "crossfade": 0.0,
                "volume": 1.0
            }
        ]

        bridge_q = c.get("bridge_question") or f"What Is {c.get('coming_up_title', f'Part {c_num + 1}')} ?"

        final_clips.append({
            "num": c_num,
            "title": title,
            "hook_quote": hook_quote,
            "coming_up_title": c.get("coming_up_title", ""),
            "start": h_start,
            "end": t_end,
            "duration": round(t_end - h_start, 2),
            "bridge_text": [bridge_q],
            "segments": segs,
            "locked": False,
            "visual_source": c.get("visual_source", default_visual_source)
        })
        cursor_time = t_end

    return final_clips

@app.command()
def transcribe(
    audio: str = typer.Option(..., help="Path to input audio file"),
    model_name: str = typer.Option("large-v3-turbo", help="Whisper model name to use (e.g. large-v3-turbo, small.en)"),
    out: str = typer.Option("transcription.json", help="Path to save transcription JSON"),
    word_timestamps: bool = typer.Option(True, help="Enable word-level timestamps")
):
    """
    Transcribe the audio file using faster-whisper (CTranslate2 INT8 with AVX-512) and cache the JSON output.
    """
    if hasattr(model_name, 'default'):
        model_name = str(model_name.default)
    if hasattr(out, 'default'):
        out = str(out.default)
    if hasattr(word_timestamps, 'default'):
        word_timestamps = bool(word_timestamps.default)

    if not os.path.exists(audio):
        typer.echo(f"Error: Audio file {audio} not found.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Loading faster-whisper model '{model_name}' (CPU int8, 8 threads)...")
    start_time = time.time()
    model = get_faster_whisper_model(model_name)
    typer.echo(f"Model ready in {time.time() - start_time:.2f} seconds.")

    typer.echo(f"Transcribing {audio} with faster-whisper (word_timestamps={word_timestamps})...")
    transcribe_start = time.time()
    audio_input = audio
    try:
        import whisper.audio
        audio_input = whisper.audio.load_audio(audio)
    except Exception:
        pass
    segments_gen, info = model.transcribe(audio_input, word_timestamps=word_timestamps)
    result = format_faster_whisper_result(segments_gen, info)
    typer.echo(f"Transcription finished in {time.time() - transcribe_start:.2f} seconds.")

    # Save raw transcription results
    out_dir_path = os.path.dirname(out)
    if out_dir_path:
        os.makedirs(out_dir_path, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)
    typer.echo(f"Saved transcription JSON to {out}")


def parse_time(time_str: str) -> float:
    time_str = time_str.strip()
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 2:  # MM:SS or MM:SS.xxx
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:  # HH:MM:SS or HH:MM:SS.xxx
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(time_str)


def build_rough_cut_segments(clip_num: int, start_time: float, end_time: float, segments: list, total_clips: int) -> dict:
    """
    Builds the canonical 4-part Rough-Cut Plan segment structure for short-form clips:
    1. Punchline / Hook Audio Segment: 15-25s quote snapped to a complete sentence start and end.
    2. Mid Transition Music Sting: Alternates between Bluesy Vibes and Howling (never deepDive-strong), 5.5s duration, 0.2s silence gap, 2.0s fade out, 0.5s crossfade into body speech.
    3. Main Body Audio Segment: Starts cleanly at the next sentence start, snapped to a complete sentence end.
    4. Outro Music Sting: deepDive-conclusion.mp3, 5.5s duration, 0.2s silence gap, 2.0s fade out.
    """
    # Gather all words across segments for word-level sentence boundary snapping
    all_words = []
    for s in segments:
        all_words.extend(s.get("words", []))

    # Sentence boundary indices
    sentence_ends = []
    for idx, w in enumerate(all_words):
        w_txt = w.get("word", "").strip()
        if any(w_txt.endswith(p) for p in [".", "?", "!"]):
            sentence_ends.append(idx)

    sentence_starts = [0]
    for idx in sentence_ends:
        if idx + 1 < len(all_words):
            sentence_starts.append(idx + 1)

    # 1. Start boundary snapping (Clean sentence start)
    if not all_words:
        start_idx = 0
        h_start = round(start_time, 2)
    elif start_time <= 0.5 or clip_num == 1:
        start_idx = 0
        h_start = round(all_words[0]["start"], 2)
    else:
        # Closest sentence start to start_time
        start_idx = min(sentence_starts, key=lambda idx: abs(all_words[idx]["start"] - start_time))
        h_start = round(all_words[start_idx]["start"], 2)

    # 2. Extract Hook Audio (15-25s snapped to complete sentence end)
    target_hook_end = h_start + 20.0
    hook_segment = None
    if all_words:
        cand_hook_ends = [idx for idx in sentence_ends if idx > start_idx]
        if cand_hook_ends:
            preferred = [idx for idx in cand_hook_ends if 12.0 <= (all_words[idx]["end"] - h_start) <= 28.0]
            if preferred:
                best_hook_idx = min(preferred, key=lambda idx: abs(all_words[idx]["end"] - target_hook_end))
            else:
                best_hook_idx = min(cand_hook_ends, key=lambda idx: abs(all_words[idx]["end"] - target_hook_end))
        else:
            best_hook_idx = min(len(all_words) - 1, start_idx + 25)

        h_end = round(all_words[best_hook_idx]["end"], 2)
        h_words = [w.get("word", "").strip() for w in all_words[start_idx : best_hook_idx + 1]]
        hook_segment = {
            "type": "audio",
            "start": h_start,
            "end": h_end,
            "duration": round(h_end - h_start, 2),
            "text": " ".join(h_words)
        }
    else:
        h_end = round(start_time + 20.0, 2)
        hook_segment = {
            "type": "audio",
            "start": h_start,
            "end": h_end,
            "duration": round(h_end - h_start, 2),
            "text": ""
        }

    # 3. Mid Transition Music Sting: Alternating Bluesy Vibes and Howling
    # Rule: NEVER use deepDive-strong in clips!
    if clip_num % 2 == 1:
        mid_music = "Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3"
    else:
        mid_music = "Howling (Sting) - Gunnar Olsen.mp3"
    mid_duration = 5.5

    # 4. Main Body Audio Segment: Starts at the very next sentence start, ends at sentence end
    if all_words and hook_segment:
        body_start_idx = best_hook_idx + 1
        if body_start_idx < len(all_words):
            main_start = round(all_words[body_start_idx]["start"], 2)
        else:
            main_start = round(h_end + 0.3, 2)
            body_start_idx = len(all_words) - 1
        h_end_acoustic = resolve_acoustic_word_end(h_end, main_start)
        hook_segment["end"] = h_end_acoustic
        hook_segment["duration"] = round(h_end_acoustic - h_start, 2)

        cand_body_ends = [idx for idx in sentence_ends if idx >= body_start_idx]
        if cand_body_ends:
            best_end_idx = min(cand_body_ends, key=lambda idx: abs(all_words[idx]["end"] - end_time))
        else:
            best_end_idx = len(all_words) - 1

        raw_main_end = round(all_words[best_end_idx]["end"], 2)
        next_w_s = all_words[best_end_idx + 1]["start"] if best_end_idx + 1 < len(all_words) else raw_main_end + 0.5
        main_end = resolve_acoustic_word_end(raw_main_end, next_w_s)
        body_words = [w.get("word", "").strip() for w in all_words[body_start_idx : best_end_idx + 1]]
        main_text = " ".join(body_words)
    else:
        main_start = round(h_end + 0.1, 2)
        main_end = round(end_time, 2)
        main_text = ""

    # Smart Dynamic Title Extraction algorithm
    clip_title = f"Part {clip_num}"
    if all_words:
        window_words = all_words[start_idx : best_end_idx + 1]
        window_text = " ".join([w.get("word", "").strip() for w in window_words])
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', window_text) if s.strip()]
        
        keywords = ["singularity", "observer", "chiral", "synchronization", "paradox", "physics", "topology", "quantum", "density", "curvature", "geometry", "information", "matter", "intelligence", "equidistance", "relativity", "autonomy", "agent", "system", "network"]
        candidate_titles = []
        for s in sentences:
            clean_s = re.sub(r'\s+', ' ', s.rstrip(".?!").strip())
            s_lower = clean_s.lower()
            score = sum(10 for kw in keywords if kw in s_lower)
            if 15 <= len(clean_s) <= 60:
                candidate_titles.append((score + 5, clean_s))
            elif len(clean_s) > 60:
                sub_parts = re.split(r'[,:;—–-]', clean_s)
                for part in sub_parts:
                    p_clean = re.sub(r'\s+', ' ', part.strip())
                    p_lower = p_clean.lower()
                    p_score = sum(10 for kw in keywords if kw in p_lower)
                    if 15 <= len(p_clean) <= 55 and p_score > 0:
                        candidate_titles.append((p_score + 8, p_clean))

        if candidate_titles:
            candidate_titles.sort(key=lambda x: x[0], reverse=True)
            chosen = candidate_titles[0][1]
            words_title = chosen.split()
            formatted = []
            for w in words_title:
                w_l = w.lower()
                if w_l in ["a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "it"]:
                    formatted.append(w_l)
                else:
                    formatted.append(w.capitalize())
            if formatted:
                formatted[0] = formatted[0].capitalize()
            clip_title = " ".join(formatted[:3])

    # Build canonical 4-part segment structure:
    # 1. Hook (audio)
    # 2. Mid Sting (music: Bluesy or Howling)
    # 3. Body (audio)
    # 4. Outro Sting (music: deepDive-conclusion.mp3)
    seg_list = [
        hook_segment,
        {
            "type": "music",
            "music_file": mid_music,
            "duration": mid_duration,
            "silence_before": 0.2,
            "gap": 0.2,
            "fade_out": 2.0,
            "crossfade": 1.0,
            "volume": 1.0
        },
        {
            "type": "audio",
            "start": main_start,
            "end": main_end,
            "duration": round(main_end - main_start, 2),
            "text": main_text
        },
        {
            "type": "music",
            "music_file": "deepDive-conclusion.mp3",
            "duration": 5.5,
            "silence_before": 0.2,
            "gap": 0.2,
            "fade_out": 2.0,
            "crossfade": 0.0,
            "volume": 1.0
        }
    ]

    bridge_question = f"What Is Part {clip_num + 1} ?"

    return {
        "num": clip_num,
        "title": clip_title,
        "start": h_start,
        "end": main_end,
        "duration": round(main_end - h_start, 2),
        "bridge_text": [bridge_question],
        "segments": seg_list,
        "locked": False,
        "visual_source": "mosaic"
    }

@app.command()
def plan(
    transcription: str = typer.Option("transcription.json", help="Path to Whisper transcription JSON"),
    audio: Optional[str] = typer.Option(None, help="Path to source audio file to get true total duration"),
    max_duration: float = typer.Option(165.0, help="Max clip duration in seconds (default 2m45s)"),
    min_duration: float = typer.Option(90.0, help="Min clip duration in seconds"),
    ranges: Optional[str] = typer.Option(None, help="Comma-separated rough start-end ranges (seconds or MM:SS, e.g. '0-1:42.5, 3:56-6:39.5')"),
    out: str = typer.Option("plan.json", help="Path to save the generated plan JSON")
):
    """
    Plan clip boundaries (either fully automated forward with integrity scoring or targeting specific ranges).
    """
    if not os.path.exists(transcription):
        typer.echo(f"Error: Transcription file {transcription} not found. Run transcribe first.", err=True)
        raise typer.Exit(code=1)

    with open(transcription, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    if not segments:
        typer.echo("Error: No segments found in transcription.", err=True)
        raise typer.Exit(code=1)

    # Determine total audio duration
    total_duration = None
    if audio and os.path.exists(audio):
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                total_duration = float(res.stdout.strip())
                typer.echo(f"True audio duration from ffprobe: {total_duration:.2f} seconds.")
        except Exception as e:
            typer.echo(f"Warning: Could not get duration via ffprobe: {e}")

    if total_duration is None:
        total_duration = segments[-1]["end"]
        typer.echo(f"Total audio duration from Whisper segments: {total_duration:.2f} seconds.")

    # Gather all word/segment boundaries for snapping (starts and ends)
    all_boundaries = []
    for seg in segments:
        words = seg.get("words", [])
        if words:
            for w in words:
                all_boundaries.append(w["start"])
                all_boundaries.append(w["end"])
        else:
            all_boundaries.append(seg["start"])
            all_boundaries.append(seg["end"])
    if 0.0 not in all_boundaries:
        all_boundaries.insert(0, 0.0)
    if total_duration not in all_boundaries:
        all_boundaries.append(total_duration)
    all_boundaries = sorted(list(set(all_boundaries)))

    clips_plan = []

    if ranges:
        typer.echo(f"Planning target ranges: {ranges}...")
        range_strs = [r.strip() for r in ranges.split(",") if r.strip()]
        for idx, r_str in enumerate(range_strs):
            parts = r_str.split("-")
            if len(parts) != 2:
                typer.echo(f"Error: Invalid range format '{r_str}'. Expected 'start-end'.", err=True)
                raise typer.Exit(code=1)
            
            try:
                r_start = parse_time(parts[0])
                r_end = parse_time(parts[1])
            except ValueError as e:
                typer.echo(f"Error parsing time in '{r_str}': {e}", err=True)
                raise typer.Exit(code=1)
            
            # Snap start to closest segment boundary
            start_aligned = min(all_boundaries, key=lambda b: abs(b - r_start))
            
            # Snap end to closest segment boundary. If it is the last range and close to the end, snap to total_duration.
            end_aligned = min(all_boundaries, key=lambda b: abs(b - r_end))
            if abs(end_aligned - total_duration) < 5.0 or r_end >= total_duration:
                end_aligned = total_duration

            duration = end_aligned - start_aligned
            if duration > max_duration:
                typer.echo(f"Warning: Aligned clip {idx + 1} duration ({duration:.2f}s) exceeds max_duration ({max_duration}s).")
            
            c_obj = build_rough_cut_segments(idx + 1, start_aligned, end_aligned, segments, len(range_strs))
            clips_plan.append(c_obj)
    else:
        spoken_clips = parse_spoken_cue_tripartite_plan(data, default_visual_source="mosaic", audio_path=audio)
        if spoken_clips:
            typer.echo(f"[Spoken Cue Caster] Detected {len(spoken_clips)} spoken tripartite clip cues! Writing plan to {out}...")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(spoken_clips, f, indent=2)
            typer.echo(f"Plan saved to {out}")
            return

        # Automated forward chronological partitioning with clip integrity focus
        boundary_candidates = []
        for idx, seg in enumerate(segments):
            text = seg.get("text", "").strip()
            end_time = seg.get("end")
            has_punctuation = text and text[-1] in [".", "?", "!"]
            
            gap = 0.0
            if idx + 1 < len(segments):
                gap = segments[idx + 1].get("start", end_time) - end_time
                if gap < 0:
                    gap = 0.0
            
            boundary_candidates.append({
                "time": end_time,
                "has_punctuation": has_punctuation,
                "gap": gap
            })

        # Calculate estimated total clip count
        estimated_clips = max(1, int(round(total_duration / ((min_duration + max_duration) / 2))))

        t_curr = 0.0
        clip_num = 1

        while t_curr < total_duration:
            candidates = [b for b in boundary_candidates if b["time"] > t_curr]
            if not candidates:
                break
            
            # Find boundaries falling in the min/max window
            valid_candidates = [b for b in candidates if min_duration <= (b["time"] - t_curr) <= max_duration]
            
            if valid_candidates:
                def get_score(b):
                    punct_score = 2.0 if b["has_punctuation"] else 0.0
                    gap_score = min(b["gap"], 1.5)
                    len_score = ((b["time"] - t_curr) / max_duration) * 0.5
                    return punct_score + gap_score + len_score
                
                target_b_candidate = max(valid_candidates, key=get_score)
                target_b = target_b_candidate["time"]
            else:
                remaining_dur = total_duration - t_curr
                if remaining_dur <= max_duration:
                    target_b = total_duration
                else:
                    target_b_candidate = min(candidates, key=lambda b: abs((b["time"] - t_curr) - max_duration))
                    target_b = target_b_candidate["time"]

            # Snap to total_duration if very close to the end
            if total_duration - target_b < 15.0:
                target_b = total_duration

            clip_duration = target_b - t_curr

            c_obj = build_rough_cut_segments(clip_num, t_curr, target_b, segments, estimated_clips)
            clips_plan.append(c_obj)

            # Move cursor based on the snapped end of the body segment
            actual_end = c_obj["segments"][2]["end"] if len(c_obj.get("segments", [])) > 2 else target_b

            if actual_end >= total_duration - 15.0 or target_b >= total_duration:
                break

            t_curr = actual_end
            clip_num += 1

    # Save plan
    with open(out, "w", encoding="utf-8") as f:
        json.dump(clips_plan, f, indent=4)

    typer.echo(f"Successfully planned {len(clips_plan)} clips.")
    for c in clips_plan:
        typer.echo(f"Clip {c['num']}: {c['start']:.2f}s -> {c['end']:.2f}s (Duration: {c['duration']:.2f}s)")
    typer.echo(f"Saved plan JSON to {out}")


@app.command()
def cut(
    audio: str = typer.Option(..., help="Path to input audio file"),
    plan_file: str = typer.Option("plan.json", help="Path to plan JSON file"),
    out_dir: str = typer.Option(".", help="Output directory for clips"),
    num: Optional[int] = typer.Option(None, "--num", "-n", help="Specific clip number to cut (cuts all clips if omitted)")
):
    """
    Cut audio file into clips based on the plan using sample-accurate re-encoding.
    """
    if hasattr(audio, 'default'):
        audio = str(audio.default)
    if hasattr(plan_file, 'default'):
        plan_file = str(plan_file.default)
    if hasattr(out_dir, 'default'):
        out_dir = str(out_dir.default)
    if hasattr(num, 'default'):
        num = num.default
    if num is not None:
        try:
            num = int(num)
        except Exception:
            num = None

    if not os.path.exists(audio):
        typer.echo(f"Error: Audio file {audio} not found.", err=True)
        raise typer.Exit(code=1)

    if not os.path.exists(plan_file):
        typer.echo(f"Error: Plan file {plan_file} not found. Run plan first.", err=True)
        raise typer.Exit(code=1)

    os.makedirs(out_dir, exist_ok=True)

    with open(plan_file, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    base_name = os.path.splitext(os.path.basename(audio))[0]
    if num is not None:
        typer.echo(f"Cutting Clip {num} from {audio}...")
    else:
        typer.echo(f"Splitting {audio} into {len(plan_data)} clips...")

    for c in plan_data:
        if num is not None and int(c.get("num", -1)) != num:
            continue
        # Naming: e.g. 242-1.mp3 or 242-1-title.mp3
        title = c.get("title", "")
        if title:
            clean_title = re.sub(r'[:\\/*?<>|"]', '', title)
            out_filename = f"{base_name}-{c['num']}-{clean_title}.mp3"
        else:
            out_filename = f"{base_name}-{c['num']}.mp3"
        out_path = os.path.join(out_dir, out_filename)

        # Convert float seconds to HH:MM:SS.xxx format for ffmpeg
        def to_time_str(secs: float) -> str:
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            s = secs % 60
            return f"{h:02d}:{m:02d}:{s:06.3f}"

        # Derive start and end times safely
        start_val = c.get("start")
        end_val = c.get("end")
        segments = c.get("segments", [])
        if start_val is None or end_val is None:
            audio_segs = [s for s in segments if s.get("type") == "audio" and "start" in s and "end" in s]
            if audio_segs:
                start_val = audio_segs[0]["start"]
                end_val = audio_segs[-1]["end"]
            else:
                start_val = 0.0
                end_val = 0.0
        start_str = to_time_str(start_val)
        end_str = to_time_str(end_val)

        has_music_seg = any(s.get("type") == "music" for s in segments)

        if has_music_seg and len(segments) > 0:
            typer.echo(f"Processing Clip {c['num']} with {len(segments)} segments (including music stings)...")

            def get_music_path(m_name: str) -> str:
                m_clean = os.path.basename(m_name)
                for cand in [
                    os.path.join("music", m_clean),
                    os.path.join("ddma", "music", m_clean),
                    os.path.join("..", "ddma", "music", m_clean),
                    os.path.join("..", "music", m_clean),
                    os.path.join("docs", "assets", "music", m_clean)
                ]:
                    if os.path.exists(cand):
                        return cand
                return os.path.join("music", m_clean)

            inputs = []
            filter_parts = []
            labels = []
            in_idx = 0
            t_cursor = 0.0

            for s_idx, seg in enumerate(segments):
                seg_type = seg.get("type")
                if seg_type == "audio":
                    s_start = float(seg.get("start", start_val))
                    s_end = float(seg.get("end", end_val))
                    s_dur = max(0.1, s_end - s_start)

                    if s_idx > 0 and segments[s_idx - 1].get("type") == "music":
                        # Music fades out over 2.0s; speech enters 1.0s before music ends at 100% FULL volume (zero afade=in on human voice!)
                        cf_dur = float(segments[s_idx - 1].get("crossfade", 1.0))
                        t_speech = max(0.0, t_cursor - cf_dur)
                        t_speech_ms = int(round(t_speech * 1000))
                        inputs.extend(["-ss", f"{s_start:.3f}", "-t", f"{s_dur:.3f}", "-i", audio])
                        filter_parts.append(
                            f"[{in_idx}:a]adelay={t_speech_ms}|{t_speech_ms}[sp{in_idx}];"
                        )
                        labels.append(f"[sp{in_idx}]")
                        t_cursor = t_speech + s_dur
                    else:
                        t_speech = t_cursor
                        t_speech_ms = int(round(t_speech * 1000))
                        inputs.extend(["-ss", f"{s_start:.3f}", "-t", f"{s_dur:.3f}", "-i", audio])
                        if t_speech_ms > 0:
                            filter_parts.append(f"[{in_idx}:a]adelay={t_speech_ms}|{t_speech_ms}[sp{in_idx}];")
                            labels.append(f"[sp{in_idx}]")
                        else:
                            labels.append(f"[{in_idx}:a]")
                        t_cursor = t_speech + s_dur
                    in_idx += 1

                elif seg_type == "music":
                    m_file = seg.get("music_file", "Howling (Sting) - Gunnar Olsen.mp3")
                    m_path = get_music_path(m_file)
                    dur_m = float(seg.get("duration", 5.5))
                    fade_out = float(seg.get("fade_out", 2.0))
                    fade_out_st = max(0.0, dur_m - fade_out)
                    silence_front = float(seg.get("silence_before", seg.get("gap", 0.2)))

                    t_sting = t_cursor + silence_front
                    t_sting_ms = int(round(t_sting * 1000))

                    inputs.extend(["-i", m_path])
                    filter_parts.append(
                        f"[{in_idx}:a]atrim=0:{dur_m:.3f},afade=t=out:st={fade_out_st:.3f}:d={fade_out:.3f},adelay={t_sting_ms}|{t_sting_ms}[m{in_idx}];"
                    )
                    labels.append(f"[m{in_idx}]")
                    in_idx += 1
                    t_cursor = t_sting + dur_m

            filter_parts.append(
                f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
            )

            cmd_mix = ["ffmpeg", "-y"] + inputs + [
                "-filter_complex", "".join(filter_parts),
                "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2",
                out_path
            ]
            res_mix = subprocess.run(cmd_mix, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_mix.returncode == 0:
                typer.echo(f"Created {out_filename} with sample-accurate sting transitions (-16 LUFS)")
            else:
                typer.echo(f"Error mixing clip {c['num']}: {res_mix.stderr}", err=True)
        else:
            cmd = [
                "ffmpeg", "-y",
                "-ss", start_str,
                "-to", end_str,
                "-i", audio,
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:a", "libmp3lame",
                "-q:a", "2",
                out_path
            ]

            typer.echo(f"Cutting Clip {c['num']}: {start_str} to {end_str}...")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if result.returncode == 0:
                typer.echo(f"Created {out_filename}")
            else:
                typer.echo(f"Error cutting clip {c['num']}: {result.stderr}", err=True)

    typer.echo("Slicing complete!")


@app.command()
def mux(
    audio: str = typer.Option(..., help="Path to input audio clip"),
    image: str = typer.Option(..., help="Path to still image canvas"),
    out: str = typer.Option(..., help="Path to save output MP4 video")
):
    """
    Mux a single audio clip with a still image to create an MP4 video (Single-Clip focus).
    """
    if not os.path.exists(audio):
        typer.echo(f"Error: Audio clip {audio} not found.", err=True)
        raise typer.Exit(code=1)

    if not os.path.exists(image):
        typer.echo(f"Error: Still image {image} not found.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Muxing {audio} and {image} into {out}...")

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image,
        "-i", audio,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        out
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        typer.echo(f"Successfully created video: {out}")
    else:
        typer.echo(f"Error creating video: {result.stderr}", err=True)
        raise typer.Exit(code=1)


@app.command()
def mux_clip(
    num: int = typer.Option(..., help="Clip number to mux"),
    plan_file: str = typer.Option("plan.json", help="Path to plan JSON file"),
    audio_dir: str = typer.Option("clips", help="Directory containing cut audio clips"),
    out_dir: str = typer.Option("clips", help="Output directory for video")
):
    """
    Mux a specific clip automatically into a solid black square draft video for Mosaic.
    """
    if not os.path.exists(plan_file):
        typer.echo(f"Error: Plan file {plan_file} not found.", err=True)
        raise typer.Exit(code=1)

    with open(plan_file, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    clip = None
    for c in plan_data:
        if c["num"] == num:
            clip = c
            break

    if not clip:
        typer.echo(f"Error: Clip {num} not found in plan.", err=True)
        raise typer.Exit(code=1)

    import glob
    # Derive episode prefix from plan_file path or plan contents if available
    ep_prefix = None
    if "episode_" in plan_file:
        parts = plan_file.split("episode_")
        if len(parts) > 1:
            ep_prefix = parts[1].split("/")[0].split("\\")[0]

    clean_title = re.sub(r'[:\\/*?<>|"]', '', clip.get("title", ""))
    if ep_prefix:
        search_pattern1 = os.path.join(audio_dir, f"{ep_prefix}-{num}.mp3")
        search_pattern2 = os.path.join(audio_dir, f"{ep_prefix}-{num}-*.mp3")
        audio_files = glob.glob(search_pattern1) + glob.glob(search_pattern2)
    else:
        audio_files = []

    if not audio_files:
        search_pattern1 = os.path.join(audio_dir, f"*-{num}.mp3")
        search_pattern2 = os.path.join(audio_dir, f"*-{num}-*.mp3")
        audio_files = glob.glob(search_pattern1) + glob.glob(search_pattern2)

    if not audio_files:
        typer.echo(f"Error: No audio file found in {audio_dir} for clip {num}.", err=True)
        raise typer.Exit(code=1)
    
    exact_match = None
    if ep_prefix and clean_title:
        candidate_exact = os.path.join(audio_dir, f"{ep_prefix}-{num}-{clean_title}.mp3")
        if os.path.exists(candidate_exact):
            exact_match = candidate_exact

    if exact_match:
        audio_path = exact_match
    else:
        audio_files.sort(key=os.path.getmtime, reverse=True)
        audio_path = audio_files[0]
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    episode = ep_prefix if ep_prefix else base_name.split("-")[0]

    os.makedirs(out_dir, exist_ok=True)
    out_filename = f"{episode}-{num}.mp4"
    out_path = os.path.join(out_dir, out_filename)

    typer.echo(f"Found audio: {audio_path}")
    typer.echo(f"Muxing into black square draft: {out_path}...")

    # Probe audio duration to guarantee canvas strictly matches audio duration
    a_dur = None
    try:
        p_a = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True
        )
        if p_a.returncode == 0 and p_a.stdout.strip():
            a_dur = float(p_a.stdout.strip())
    except Exception:
        pass

    # Mux using FFmpeg color source filter to generate a 1080x1080 black video dynamically at standard 30fps
    if a_dur:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s=1080x1080:r=30:d={a_dur:.3f}",
            "-i", audio_path,
            "-r", "30",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", f"{a_dur:.3f}",
            out_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=black:s=1080x1080:r=30",
            "-i", audio_path,
            "-r", "30",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out_path
        ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode == 0:
        typer.echo(f"Successfully created draft video: {out_path}")
    else:
        typer.echo(f"Error creating video: {result.stderr}", err=True)
        raise typer.Exit(code=1)


_FASTER_WHISPER_MODELS = {}

def patch_pyav_metadata_errors():
    """Ensure PyAV 14+ does not raise TypeError on unexpected 'metadata_errors' keyword argument."""
    try:
        import av
        if not hasattr(av, "_patched_metadata_errors"):
            _orig_open = av.open
            def _safe_av_open(*args, **kwargs):
                kwargs.pop("metadata_errors", None)
                return _orig_open(*args, **kwargs)
            av.open = _safe_av_open
            av._patched_metadata_errors = True
    except Exception:
        pass

def format_faster_whisper_result(segments_gen, info) -> dict:
    segments_list = []
    text_chunks = []
    for s in segments_gen:
        text_chunks.append(s.text)
        seg_dict = {
            "id": getattr(s, "id", len(segments_list)),
            "seek": getattr(s, "seek", 0),
            "start": round(float(s.start), 3),
            "end": round(float(s.end), 3),
            "text": s.text,
            "tokens": getattr(s, "tokens", []),
            "avg_logprob": getattr(s, "avg_logprob", 0.0),
            "compression_ratio": getattr(s, "compression_ratio", 1.0),
            "no_speech_prob": getattr(s, "no_speech_prob", 0.0),
        }
        if s.words:
            seg_dict["words"] = [
                {
                    "word": w.word,
                    "start": round(float(w.start), 3),
                    "end": round(float(w.end), 3),
                    "probability": round(float(getattr(w, "probability", 1.0)), 4)
                }
                for w in s.words
            ]
        else:
            seg_dict["words"] = []
        segments_list.append(seg_dict)

    return {
        "text": "".join(text_chunks).strip(),
        "segments": segments_list,
        "language": getattr(info, "language", "en")
    }

def get_faster_whisper_model(model_name: str = "large-v3-turbo"):
    global _FASTER_WHISPER_MODELS
    patch_pyav_metadata_errors()
    fw_model_name = model_name or "large-v3-turbo"
    if fw_model_name not in _FASTER_WHISPER_MODELS:
        from faster_whisper import WhisperModel
        _FASTER_WHISPER_MODELS[fw_model_name] = WhisperModel(
            fw_model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=8
        )
    return _FASTER_WHISPER_MODELS[fw_model_name]


def ensure_dejavu_font() -> str:
    """Ensure DejaVuSansMono.ttf is available in local fonts/ folder for libass."""
    fonts_dir = "fonts"
    os.makedirs(fonts_dir, exist_ok=True)
    ttf_path = os.path.join(fonts_dir, "DejaVuSansMono.ttf")
    if not os.path.exists(ttf_path):
        try:
            import urllib.request
            import zipfile
            import io
            url = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
            data = urllib.request.urlopen(url, timeout=15).read()
            z = zipfile.ZipFile(io.BytesIO(data))
            for n in z.namelist():
                if n.endswith(("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf")):
                    with open(os.path.join(fonts_dir, os.path.basename(n)), "wb") as f_out:
                        f_out.write(z.read(n))
        except Exception as e:
            typer.echo(f"Warning downloading DejaVuSansMono.ttf: {e}")
    return fonts_dir


def format_ass_time(seconds: float) -> str:
    """Format seconds as h:mm:ss.cc for ASS Dialogue events."""
    seconds = max(0.0, float(seconds))
    total_cs = int(round(seconds * 100))
    h = total_cs // 360000
    rem = total_cs % 360000
    m = rem // 6000
    rem = rem % 6000
    s = rem // 100
    cs = rem % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def extract_clip_words(clip: dict, plan_file: str, audio_path: Optional[str] = None, force_whisper: bool = False) -> list:
    """
    Extract word-level timestamps in rendered clip body coordinates (0..body_duration).
    Uses faster-whisper large-v3-turbo when force_whisper=True or when transcription.json is absent,
    and caches on clip['_caption_words'] keyed by _audio_sig.
    """
    import hashlib
    audio_sig = hashlib.md5(json.dumps(clip.get("segments", []), sort_keys=True).encode("utf-8")).hexdigest()
    if not force_whisper and clip.get("_caption_words_sig") == audio_sig and clip.get("_caption_words"):
        return clip["_caption_words"]

    words = []
    if force_whisper and audio_path and os.path.exists(audio_path):
        try:
            audio_arr = whisper.audio.load_audio(audio_path) if (whisper and hasattr(whisper, 'audio')) else audio_path
            typer.echo(f"Running faster-whisper large-v3-turbo word-level transcription on {audio_path}...")
            model = get_faster_whisper_model()
            segments_gen, _ = model.transcribe(audio_arr, word_timestamps=True)
            for s in segments_gen:
                for w in (s.words or []):
                    w_txt = w.word.strip()
                    if w_txt:
                        words.append({
                            "word": w_txt,
                            "start": round(float(w.start), 2),
                            "end": round(float(w.end), 2)
                        })
        except Exception as e:
            typer.echo(f"Warning running faster-whisper on {audio_path}: {e}")

    # Fast segment-aware mapping from project transcription.json (respects reordered segments & crossfades)
    if not words:
        proj_dir = os.path.dirname(plan_file) if plan_file else ""
        trans_candidates = []
        if proj_dir:
            trans_candidates.append(os.path.join(proj_dir, "transcription.json"))
        import re
        ep_match = re.search(r"episodes?[_/\\](\d+)", str(plan_file))
        if ep_match:
            ep_id = ep_match.group(1)
            trans_candidates.append(os.path.join("projects", f"episode_{ep_id}", "transcription.json"))
            trans_candidates.append(os.path.join("docs", "episodes", ep_id, "transcription.json"))
        trans_candidates.append("transcription.json")

        trans_path = next((p for p in trans_candidates if os.path.exists(p)), None)
        if trans_path:
            try:
                with open(trans_path, "r", encoding="utf-8") as tf:
                    trans_data = json.load(tf)
                all_ep_words = []
                for seg in trans_data.get("segments", []):
                    for w in seg.get("words", []):
                        all_ep_words.append(w)

                segments = clip.get("segments", [])
                if segments:
                    t_cursor = 0.0
                    for idx, s in enumerate(segments):
                        dur = float(s.get("duration", 0.0))
                        if s.get("type") == "audio":
                            s_start = float(s.get("start", 0.0))
                            s_end = float(s.get("end", 0.0))
                            eff_dur = s_end - s_start if s_end > s_start else dur
                            if idx > 0 and segments[idx - 1].get("type") == "music":
                                cf = float(segments[idx - 1].get("crossfade", 1.0))
                                t_speech_start = max(0.0, t_cursor - cf)
                            else:
                                t_speech_start = t_cursor
                            for w in all_ep_words:
                                ws = float(w.get("start", 0.0))
                                we = float(w.get("end", ws))
                                w_mid = (ws + we) / 2.0
                                if s_start <= w_mid <= s_end:
                                    rel_s = max(0.0, ws - s_start)
                                    rel_e = min(eff_dur, max(rel_s + 0.04, we - s_start))
                                    w_txt = str(w.get("word", "")).strip()
                                    if w_txt:
                                        words.append({
                                            "word": w_txt,
                                            "start": round(t_speech_start + rel_s, 2),
                                            "end": round(t_speech_start + rel_e, 2)
                                        })
                            t_cursor = t_speech_start + eff_dur
                        elif s.get("type") == "music":
                            silence_front = float(s.get("silence_before", s.get("gap", 0.2)))
                            t_cursor = t_cursor + silence_front + dur
                else:
                    c_start = float(clip.get("start", 0.0))
                    c_end = float(clip.get("end", 0.0))
                    for w in all_ep_words:
                        ws = float(w.get("start", 0.0))
                        we = float(w.get("end", ws))
                        w_mid = (ws + we) / 2.0
                        if c_start <= w_mid <= c_end:
                            w_txt = str(w.get("word", "")).strip()
                            if w_txt:
                                words.append({
                                    "word": w_txt,
                                    "start": round(max(0.0, ws - c_start), 2),
                                    "end": round(max(0.04, we - c_start), 2)
                                })
            except Exception as e:
                typer.echo(f"Warning mapping words from transcription.json: {e}")

    # Final fallback to faster-whisper small.en if words still empty and audio_path exists
    if not words and audio_path and os.path.exists(audio_path):
        try:
            audio_arr = whisper.audio.load_audio(audio_path) if (whisper and hasattr(whisper, 'audio')) else audio_path
            typer.echo(f"Transcribing {audio_path} with faster-whisper large-v3-turbo...")
            model = get_faster_whisper_model()
            segments_gen, _ = model.transcribe(audio_arr, word_timestamps=True)
            for s in segments_gen:
                for w in (s.words or []):
                    w_txt = w.word.strip()
                    if w_txt:
                        words.append({
                            "word": w_txt,
                            "start": round(float(w.start), 2),
                            "end": round(float(w.end), 2)
                        })
        except Exception as e:
            typer.echo(f"Warning in faster-whisper fallback: {e}")

    if words:
        clip["_caption_words"] = words
        clip["_caption_words_sig"] = audio_sig
    return words


def align_text_to_words(edited_text: str, raw_words: list) -> list:
    """
    Align user-edited clip.text onto word-level timestamps so spelling fixes and edits
    appear in the burned captions at the exact spoken timestamps.
    """
    if not raw_words:
        return []
    if not edited_text or not edited_text.strip():
        return [dict(w) for w in raw_words]

    import difflib
    import re

    edited_tokens = [t.strip() for t in re.split(r"\s+", edited_text.strip()) if t.strip()]
    if not edited_tokens:
        return [dict(w) for w in raw_words]

    def norm_tok(t: str) -> str:
        return re.sub(r"[^a-z0-9]", "", t.lower())

    raw_norms = [norm_tok(w["word"]) for w in raw_words]
    edit_norms = [norm_tok(t) for t in edited_tokens]

    matcher = difflib.SequenceMatcher(None, raw_norms, edit_norms, autojunk=False)
    aligned = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                rw = raw_words[i1 + k]
                aligned.append({
                    "word": edited_tokens[j1 + k],
                    "start": rw["start"],
                    "end": rw["end"]
                })
        elif tag == "replace":
            span_start = raw_words[i1]["start"]
            span_end = raw_words[i2 - 1]["end"]
            count = j2 - j1
            step = max(0.04, (span_end - span_start) / max(1, count))
            for k in range(count):
                s_t = round(span_start + k * step, 2)
                e_t = round(span_start + (k + 1) * step, 2)
                aligned.append({
                    "word": edited_tokens[j1 + k],
                    "start": s_t,
                    "end": max(s_t + 0.04, e_t)
                })
        elif tag == "insert":
            anchor_t = raw_words[i1]["start"] if i1 < len(raw_words) else raw_words[-1]["end"]
            count = j2 - j1
            step = 0.12
            for k in range(count):
                s_t = round(anchor_t + k * step, 2)
                aligned.append({
                    "word": edited_tokens[j1 + k],
                    "start": s_t,
                    "end": round(s_t + step, 2)
                })
        elif tag == "delete":
            # User deleted these words from the caption script
            pass

    return aligned if aligned else [dict(w) for w in raw_words]


def build_caption_chunks(
    words: list,
    intro_offset: float = 1.5,
    body_duration: Optional[float] = None,
    has_outro: bool = True
) -> list:
    """
    Build timed caption chunks according to the deepDive vertical-render spec:
    - Coverage: spoken body only (skip ~1.5s title intro and ~5s outro card).
    - Chunking: 3–6 words (occasionally up to 8), <=34 characters each, single-line.
    - Chaining: each event's end time = the next event's start time (no gaps, no overlaps).
    - Text: all lowercase, natural punctuation preserved.
    """
    if not words:
        return []

    min_t = float(intro_offset)
    if body_duration is not None and body_duration > 0:
        # Outro is 5s with a 1s crossfade starting at body_duration - 1.0 in body coordinates
        max_t = float(intro_offset) + float(body_duration) - (1.0 if has_outro else 0.0)
    else:
        max_t = float(intro_offset) + float(words[-1]["end"]) + 1.0

    # Shift words into compiled video timeline (+intro_offset) and filter to spoken body coverage
    shifted_words = []
    for w in words:
        w_text = " ".join(str(w.get("word", "")).split()).lower()
        if not w_text:
            continue
        ws = round(float(w["start"]) + min_t, 2)
        we = round(float(w["end"]) + min_t, 2)
        if ws >= max_t - 0.05:
            continue
        ws = max(min_t, ws)
        we = min(max_t, max(ws + 0.04, we))
        shifted_words.append({"word": w_text, "start": ws, "end": we})

    if not shifted_words:
        return []

    # Group into phrase chunks of 3-6 words, <= 34 characters
    raw_groups = []
    curr_group = []

    for w in shifted_words:
        w_tok = w["word"]
        if len(w_tok) > 34:
            w_tok = w_tok[:34]
            w = dict(w, word=w_tok)

        if not curr_group:
            curr_group.append(w)
            continue

        cand_text = " ".join([x["word"] for x in curr_group] + [w_tok])
        if len(cand_text) > 34 or len(curr_group) >= 6:
            raw_groups.append(curr_group)
            curr_group = [w]
            continue

        curr_group.append(w)
        # Break naturally at punctuation once we have 3–6 words
        if len(curr_group) >= 3 and w_tok[-1] in (".", ",", ";", ":", "?", "!"):
            raw_groups.append(curr_group)
            curr_group = []

    if curr_group:
        raw_groups.append(curr_group)

    # Rebalance or merge any 1-2 word orphan chunks where possible while keeping <= 34 chars and <= 8 words
    balanced_groups = []
    for grp in raw_groups:
        if balanced_groups and len(grp) <= 2:
            prev = balanced_groups[-1]
            merged_text = " ".join([x["word"] for x in prev + grp])
            if len(merged_text) <= 34 and len(prev) + len(grp) <= 8:
                balanced_groups[-1] = prev + grp
                continue
            elif len(prev) >= 4:
                # Try shifting last word of prev to start of grp so both have >= 2-3 words
                cand_prev = prev[:-1]
                cand_curr = [prev[-1]] + grp
                if len(" ".join(x["word"] for x in cand_curr)) <= 34:
                    balanced_groups[-1] = cand_prev
                    balanced_groups.append(cand_curr)
                    continue
        balanced_groups.append(grp)

    chunks = []
    for grp in balanced_groups:
        text_line = " ".join(x["word"] for x in grp).replace("\n", " ").strip().lower()
        if len(text_line) > 34:
            text_line = text_line[:34].rstrip()
        chunks.append({
            "start": round(grp[0]["start"], 2),
            "end": round(grp[-1]["end"], 2),
            "text": text_line,
            "words": [{"word": x["word"], "start": round(x["start"], 2), "end": round(x["end"], 2)} for x in grp]
        })

    # Strict chaining: each event's end time = the next event's start time (no gaps, no overlaps)
    for i in range(len(chunks) - 1):
        next_start = round(chunks[i + 1]["start"], 2)
        if next_start <= chunks[i]["start"]:
            next_start = round(chunks[i]["start"] + 0.08, 2)
            chunks[i + 1]["start"] = next_start
        chunks[i]["end"] = next_start

    if chunks:
        last_end = max(round(chunks[-1]["start"] + 0.25, 2), min(round(max_t, 2), round(chunks[-1]["end"] + 0.15, 2)))
        chunks[-1]["end"] = last_end

    return chunks


def write_ass_file(
    chunks: list,
    ass_path: str,
    body_duration: float = 0.0,
    intro_offset: float = 0.0,
    visual_source: str = "mosaic"
):
    """Write exact ASS v4+ caption file for 1080x1920 vertical canvas with studio ribbon above captions."""
    os.makedirs(os.path.dirname(ass_path) if os.path.dirname(ass_path) else ".", exist_ok=True)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Caption,DejaVu Sans Mono,46,&H00FFFFFF,&H000019FF,&H80000000,&H80000000,1,0,0,0,100,100,1.2,0,1,2,0,8,60,60,465,1",
        "Style: HostRibbon,Arial,17,&H00CBD5E1,&H00CBD5E1,&H00000000,&H00000000,1,0,0,0,100,100,2.5,0,1,0,0,5,40,40,60,1",
        "Style: MicShape,Arial,18,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,40,40,60,1",
        "Style: FooterBar,DejaVu Sans Mono,18,&H008B7464,&H008B7464,&H00000000,&H00000000,0,0,0,0,100,100,0.5,0,1,0,0,5,40,40,60,1",
        "Style: FooterLine,Arial,1,&H00554133,&H00554133,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,40,40,60,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]
    mic_shape = 'm -10 -24 b -10 -32 10 -32 10 -24 l 10 0 b 10 7 -10 7 -10 0 l -10 -24 m -14 -5 b -14 13 14 13 14 -5 l 16 -5 b 16 17 -16 17 -16 -5 l -14 -5 m -2 15 l 2 15 l 2 23 l 11 23 l 11 26 l -11 26 l -11 23 l -2 23'
    c_gold = r"{\c&H000AD6FF&}"
    c_white = r"{\c&H00FFFFFF&}"
    c_dim = r"{\c&H00757575&}"

    total_end = intro_offset + (body_duration if body_duration > 0 else (chunks[-1]["end"] if chunks else 120.0))
    s_start_ribbon = format_ass_time(intro_offset)
    s_end_ribbon = format_ass_time(total_end)

    # Broadcast studio header ribbon brought slightly down to y=405 (cleanly above captions at y=465..515)
    y_ribbon = 405
    y_mic = 404
    header_events = [
        f"Dialogue: 1,{s_start_ribbon},{s_end_ribbon},HostRibbon,,0,0,0,,{{\\pos(420,{y_ribbon})\\an6\\c&H00E2E8F0&\\b1\\fsp3}}SATOSHA",
        f"Dialogue: 1,{s_start_ribbon},{s_end_ribbon},HostRibbon,,0,0,0,,{{\\pos(660,{y_ribbon})\\an4\\c&H00E2E8F0&\\b1\\fsp3}}SATOSHI",
        f"Dialogue: 1,{s_start_ribbon},{s_end_ribbon},HostRibbon,,0,0,0,,{{\\pos(475,{y_mic})\\an5\\c&H00475569&}}─",
        f"Dialogue: 1,{s_start_ribbon},{s_end_ribbon},HostRibbon,,0,0,0,,{{\\pos(605,{y_mic})\\an5\\c&H00475569&}}─",
    ]

    period = 0.8
    t_curr = intro_offset
    while t_curr < total_end:
        t_on_start = t_curr
        t_on_end = min(total_end, t_curr + 0.48)
        t_off_start = t_on_end
        t_off_end = min(total_end, t_curr + period)

        s_on = format_ass_time(t_on_start)
        e_on = format_ass_time(t_on_end)
        header_events.append(f"Dialogue: 2,{s_on},{e_on},MicShape,,0,0,0,,{{\\pos(540,{y_mic})\\an5\\fscx60\\fscy60\\c&H00FFFFFF&\\p1}}{mic_shape}{{\\p0}}")

        if t_off_start < t_off_end:
            s_off = format_ass_time(t_off_start)
            e_off = format_ass_time(t_off_end)
            header_events.append(f"Dialogue: 2,{s_off},{e_off},MicShape,,0,0,0,,{{\\pos(540,{y_mic})\\an5\\fscx60\\fscy60\\c&H00334155&\\p1}}{mic_shape}{{\\p0}}")

        t_curr += period

    for ch in (chunks or []):
        c_start = float(ch.get("start", 0.0))
        c_end = float(ch.get("end", c_start + 1.0))
        words = ch.get("words")

        if words and isinstance(words, list) and len(words) > 1:
            for i, w in enumerate(words):
                w_start_val = max(c_start, float(w.get("start", c_start)))
                if i < len(words) - 1:
                    w_end_val = min(c_end, max(w_start_val + 0.04, float(words[i + 1].get("start", w_start_val + 0.2))))
                else:
                    w_end_val = c_end

                start_str = format_ass_time(w_start_val)
                end_str = format_ass_time(w_end_val)

                passed = " ".join(str(x.get("word", "")).strip().lower() for x in words[:i])
                active = str(words[i].get("word", "")).strip().lower()
                upcoming = " ".join(str(x.get("word", "")).strip().lower() for x in words[i + 1:])

                parts = []
                if passed:
                    parts.append(f"{c_white}{passed}")
                parts.append(f"{c_gold}{active}{c_white}")
                if upcoming:
                    parts.append(f"{c_dim}{upcoming}{c_white}")

                line_txt = " ".join(parts)
                lines.append(f"Dialogue: 0,{start_str},{end_str},Caption,,0,0,0,,{line_txt}")
        else:
            start_str = format_ass_time(c_start)
            end_str = format_ass_time(c_end)
            txt = str(ch.get("text", "")).replace("\n", " ").strip().lower()
            if txt:
                lines.append(f"Dialogue: 0,{start_str},{end_str},Caption,,0,0,0,,{txt}")

    lines.extend(header_events)

    # Bottom footer bar strip (subtle horizontal delimiter line at y=1336 directly below central 740x740 deck, left source label, right deepDive podcast)
    left_label = "Archetype: KineticVector" if visual_source == "manim" else "Mosaic"
    footer_events = [
        f"Dialogue: 1,{s_start_ribbon},{s_end_ribbon},FooterLine,,0,0,0,,{{\\pos(540,1336)\\an5\\c&H00554133&\\p1}}m -370 -1 l 370 -1 l 370 1 l -370 1{{\\p0}}",
        f"Dialogue: 1,{s_start_ribbon},{s_end_ribbon},FooterBar,,0,0,0,,{{\\pos(170,1355)\\an4\\c&H008B7464&}}{left_label}",
        f"Dialogue: 1,{s_start_ribbon},{s_end_ribbon},FooterBar,,0,0,0,,{{\\pos(910,1355)\\an6\\c&H008B7464&}}deepDive podcast",
    ]
    lines.extend(footer_events)

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def generate_clip_captions(
    clip: dict,
    plan_file: str,
    audio_path: Optional[str] = None,
    intro_offset: float = 1.5,
    body_duration: Optional[float] = None,
    has_outro: bool = True,
    force_whisper: bool = False,
    force_realign: bool = False
) -> list:
    """
    Ensure clip['caption_chunks'] is populated and up to date with clip['segments'] and clip['text'].
    """
    import hashlib
    caption_sig = hashlib.md5(json.dumps({
        "segments": clip.get("segments", []),
        "text": clip.get("text", ""),
        "intro_offset": intro_offset,
        "has_outro": has_outro
    }, sort_keys=True).encode("utf-8")).hexdigest()

    if not force_whisper and not force_realign and clip.get("_caption_sig") == caption_sig and isinstance(clip.get("caption_chunks"), list) and len(clip["caption_chunks"]) > 0:
        return clip["caption_chunks"]

    raw_words = extract_clip_words(clip, plan_file=plan_file, audio_path=audio_path, force_whisper=force_whisper)
    edited_text = clip.get("text", "")
    aligned_words = align_text_to_words(edited_text, raw_words)
    chunks = build_caption_chunks(aligned_words, intro_offset=intro_offset, body_duration=body_duration, has_outro=has_outro)
    clip["caption_chunks"] = chunks
    clip["_caption_sig"] = caption_sig
    return chunks


@app.command()
def compile_clip(
    num: int = typer.Option(..., help="Clip number to compile"),
    plan_file: str = typer.Option("plan.json", help="Path to plan JSON file"),
    master_dir: str = typer.Option("clips", help="Directory containing the finished master clips"),
    music: str = typer.Option("title-card-music.mp3", help="Path to the custom audio intro track"),
    out_dir: str = typer.Option("clips", help="Output directory for the compiled video"),
    font_path: Optional[str] = typer.Option(None, help="Optional path to custom TrueType font"),
    backup: bool = typer.Option(True, help="Create a backup of the original master clip"),
    episode_title: str = typer.Option("Life, Death and the Lysosome", help="Title of the episode"),
    force_draft: bool = typer.Option(False, help="Force black canvas draft body compilation even if Mosaic video exists"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Visual source engine: 'mosaic' or 'manim'")
):
    """
    Mux and compile a clip with dynamic title card intro and finished Mosaic video.
    """
    import shutil
    import glob

    if hasattr(num, 'default'): num = int(num.default)
    if hasattr(plan_file, 'default'): plan_file = str(plan_file.default)
    if hasattr(master_dir, 'default'): master_dir = str(master_dir.default)
    if hasattr(music, 'default'): music = str(music.default)
    if not os.path.exists(music):
        fallback_candidates = [
            "music/deepDive-soft-ok.mp3",
                        "music/deepDive-main.mp3"
        ]
        for cand in fallback_candidates:
            if os.path.exists(cand):
                music = cand
                break

    if hasattr(out_dir, 'default'): out_dir = str(out_dir.default)
    if hasattr(font_path, 'default'): font_path = font_path.default
    if hasattr(backup, 'default'): backup = bool(backup.default)
    if hasattr(episode_title, 'default'): episode_title = str(episode_title.default)
    if hasattr(force_draft, 'default'): force_draft = bool(force_draft.default)
    if hasattr(source, 'default'): source = source.default

    temp_img_path = f"temp_title_{num}.png"
    intro_video_path = f"temp_intro_{num}.mp4"
    concat_txt_path = f"temp_concat_{num}.txt"
    temp_extracted_frame = f"temp_extracted_{num}.png"
    temp_body_path = f"temp_body_{num}.mp4"
    temp_img_outro_path = f"temp_outro_{num}.png"
    temp_outro_video_path = f"temp_outro_{num}.mp4"

    if not os.path.exists(plan_file):
        typer.echo(f"Error: Plan file {plan_file} not found.", err=True)
        raise typer.Exit(code=1)

    with open(plan_file, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    clip = None
    for c in plan_data:
        if c["num"] == num:
            clip = c
            break

    if not clip:
        typer.echo(f"Error: Clip {num} not found in plan.", err=True)
        raise typer.Exit(code=1)

    # Keep dedicated title card music (e.g. title-card-music.mp3 or deepDive-soft-ok.mp3) for the 1.5s Intro Card
    # Never overwrite `music` with the mid-sting (Bluesy Vibes / Howling) from clip["segments"]!

    # 1. Locate the master clip (e.g. clips/245-4.mp4)
    ep_prefix = None
    if "episode_" in plan_file:
        parts = plan_file.split("episode_")
        if len(parts) > 1:
            ep_prefix = parts[1].split("/")[0].split("\\")[0]

    if ep_prefix:
        search_pattern = os.path.join(master_dir, f"{ep_prefix}-{num}.mp4")
        master_files = [f for f in glob.glob(search_pattern) if not f.endswith("-original.mp4")]
    else:
        master_files = []

    if not master_files:
        typer.echo(f"No video file found for clip {num} in {master_dir}. Auto-muxing solid black canvas draft...")
        mux_clip(num=num, plan_file=plan_file, audio_dir=master_dir, out_dir=out_dir)
        if ep_prefix:
            search_pattern = os.path.join(master_dir, f"{ep_prefix}-{num}.mp4")
            master_files = [f for f in glob.glob(search_pattern) if not f.endswith("-original.mp4")]
        if not master_files:
            search_pattern = os.path.join(master_dir, f"*-{num}.mp4")
            master_files = [f for f in glob.glob(search_pattern) if not f.endswith("-original.mp4")]

    if not master_files:
        typer.echo(f"Error: Could not generate or locate video file in {master_dir} for clip {num}.", err=True)
        raise typer.Exit(code=1)

    master_path = master_files[0]
    base_name = os.path.splitext(os.path.basename(master_path))[0]
    episode = ep_prefix if ep_prefix else base_name.split("-")[0]

    backup_path = os.path.join(master_dir, f"{base_name}-original.mp4")

    # 2. Resolve episode title from project_info.json if available
    proj_dir_from_plan = os.path.dirname(plan_file)
    info_p = os.path.join(proj_dir_from_plan, "project_info.json") if proj_dir_from_plan else ""
    if info_p and os.path.exists(info_p):
        try:
            with open(info_p, "r", encoding="utf-8") as ipf:
                info_d = json.load(ipf)
                if info_d.get("title"):
                    episode_title = info_d["title"]
        except Exception:
            pass

    target_clip = next((c for c in plan_data if c.get("num") == num), None)
    mosaic_run_id = target_clip.get("mosaic_run_id") if target_clip else None
    
    # Active master setting from plan.json
    active_master_src = str(target_clip.get("visual_source", "mosaic") if target_clip else "mosaic").lower()
    if active_master_src in ("infographic", "manim"):
        active_master_src = "manim"
    else:
        active_master_src = "mosaic"

    # Explicit compile source override if passed via CLI, else active_master_src
    if source:
        compile_source = "manim" if str(source).lower() in ("manim", "infographic") else "mosaic"
    else:
        compile_source = active_master_src

    infographic_candidates = [
        f"clips/{episode}-{num}-infographic.mp4",
        f"clips/{episode}-{num}-manim.mp4",
    ]
    mosaic_candidates = []
    if mosaic_run_id:
        mosaic_candidates.append(f"clips/{episode}-{num}-mosaic-{mosaic_run_id}.mp4")
    mosaic_candidates.extend([
        f"clips/{episode}-{num}-original.mp4",
        f"clips/{episode}-{num}-mosaic.mp4",
    ])

    if compile_source == "manim":
        chosen_body = next((p for p in infographic_candidates if os.path.exists(p) and os.path.getsize(p) > 10000), None)
        if chosen_body:
            backup_path = chosen_body
            has_motion_source = True
        else:
            backup_path = f"clips/{episode}-{num}.mp4"
            has_motion_source = False
    else:
        chosen_body = next((p for p in mosaic_candidates if os.path.exists(p) and os.path.getsize(p) > 10000), None)
        if chosen_body:
            backup_path = chosen_body
            has_motion_source = True
        else:
            backup_path = f"clips/{episode}-{num}.mp4"
            has_motion_source = False

    # Check for freshly cut audio clip (e.g. clips/245-1-*.mp3) and remux audio track
    audio_pattern1 = os.path.join(master_dir, f"{episode}-{num}-*.mp3")
    audio_pattern2 = os.path.join(master_dir, f"{episode}-{num}.mp3")
    audio_matches = glob.glob(audio_pattern1) + glob.glob(audio_pattern2)
    if not audio_matches:
        audio_matches = glob.glob(os.path.join(master_dir, f"*-{num}-*.mp3")) + glob.glob(os.path.join(master_dir, f"*-{num}.mp3"))
    
    temp_remux_path = f"temp_remux_{num}.mp4"
    temp_body_path = f"temp_body_{num}.mp4"
    has_mosaic_file = has_motion_source and os.path.exists(backup_path)
    
    # A clip is a black canvas draft if force_draft is requested OR if neither Infographic nor Mosaic video exists
    is_black_canvas = force_draft or not has_mosaic_file

    a_dur_fresh = None
    fps_str = "30"

    if audio_matches:
        audio_matches.sort(key=os.path.getmtime, reverse=True)
        fresh_audio_path = audio_matches[0]
        typer.echo(f"Updating master body audio from fresh audio clip: {fresh_audio_path}...")
        try:
            p_a = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", fresh_audio_path], capture_output=True, text=True)
            if p_a.returncode == 0:
                a_dur_fresh = float(p_a.stdout.strip())
            if has_mosaic_file:
                p_v = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=r_frame_rate,avg_frame_rate,duration", "-of", "json", backup_path], capture_output=True, text=True)
                if p_v.returncode == 0:
                    v_data = json.loads(p_v.stdout)
                    for st in v_data.get("streams", []):
                        if st.get("codec_type") == "video":
                            fps_cand = st.get("avg_frame_rate") or st.get("r_frame_rate")
                            if fps_cand and "/" in fps_cand and fps_cand != "0/0":
                                fps_str = fps_cand
                            break
        except Exception as ex_probe:
            typer.echo(f"Warning probing durations: {ex_probe}")

        if is_black_canvas:
            typer.echo(f"Generating clean draft body video ({a_dur_fresh:.2f}s) from fresh audio clip...")
            cmd_remux = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s=1080x1080:r={fps_str}:d={a_dur_fresh:.3f}",
                "-i", fresh_audio_path,
                "-r", fps_str,
                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-t", f"{a_dur_fresh:.3f}",
                temp_remux_path
            ]
            res_remux = subprocess.run(cmd_remux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_remux.returncode == 0:
                body_video_path = temp_remux_path
        else:
            typer.echo(f"Preserving Mosaic motion graphics video track from {backup_path}...")
            cmd_remux = [
                "ffmpeg", "-y",
                "-i", backup_path,
                "-i", fresh_audio_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", f"{a_dur_fresh:.3f}" if a_dur_fresh else "0",
                temp_remux_path
            ]
            res_remux = subprocess.run(cmd_remux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_remux.returncode == 0:
                body_video_path = temp_remux_path
            else:
                body_video_path = backup_path

    # 3. Get title
    title = clip.get("title", "")
    if not title:
        typer.echo(f"Warning: No title specified for clip {num} in plan.json.")

    # 4. Generate dynamic title card image
    from PIL import Image, ImageDraw, ImageFont
    temp_img_path = f"temp_title_{num}.png"
    intro_video_path = f"temp_intro_{num}.mp4"
    concat_txt_path = f"temp_concat_{num}.txt"
    temp_extracted_frame = f"temp_extracted_{num}.png"

    try:
        # Helpers defined inside compile_clip
        def wrap_text(text, font, max_width, draw_obj):
            words = text.split()
            lines = []
            current_line = []
            for word in words:
                test_line = " ".join(current_line + [word])
                bbox = draw_obj.textbbox((0, 0), test_line, font=font)
                test_width = bbox[2] - bbox[0]
                if test_width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            return lines

        def find_system_fonts():
            candidates = [
                (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
                (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
                ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
                ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
                ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
            ]
            for reg, bold in candidates:
                if os.path.exists(reg) and os.path.exists(bold):
                    return reg, bold
            return None, None

        # Open image canvas with clean solid charcoal background
        from PIL import Image, ImageDraw, ImageFont
        width, height = 1080, 1080
        bg_color = (0, 0, 0, 255)
        image = Image.new("RGBA", (width, height), bg_color)

        draw_overlay = ImageDraw.Draw(image)

        # Resolve fonts
        font_path_reg, font_path_bold = find_system_fonts()
        if font_path and os.path.exists(font_path):
            font_path_reg = font_path
            font_path_bold = font_path

        try:
            if font_path_reg and font_path_bold:
                font_sub = ImageFont.truetype(font_path_reg, 28)
                font_title = ImageFont.truetype(font_path_bold, 48)
            else:
                raise Exception("No standard system fonts found")
        except Exception as e:
            typer.echo(f"Warning loading TrueType fonts: {e}. Falling back to default.")
            font_sub = ImageFont.load_default()
            font_title = ImageFont.load_default()

        # Dynamic episode title resolution
        ep_title = episode_title
        proj_dir = os.path.dirname(plan_file) if plan_file and os.path.dirname(plan_file) else os.path.join("projects", f"episode_{episode}")
        proj_info_path = os.path.join(proj_dir, "project_info.json")
        if os.path.exists(proj_info_path):
            try:
                with open(proj_info_path, "r", encoding="utf-8") as pif:
                    pinfo = json.load(pif)
                    if pinfo.get("title"):
                        ep_title = pinfo.get("title")
                    elif pinfo.get("name") and episode_title == "Life, Death and the Lysosome":
                        ep_title = pinfo.get("name")
            except Exception:
                pass

        sub_text = f"EPISODE {episode}" if num == 0 else f"EPISODE {episode} • PART {num}"
        title_text = title if title else (ep_title if num == 0 else f"Part {num}")

        # Pure Glossy Black (#000000) canvas per Monochrome Noir standard — zero gray banner box
        box_width = int(width * 0.88)
        box_height = 320
        x0 = (width - box_width) // 2
        y0 = height // 2 - 180
        x1 = x0 + box_width
        y1 = y0 + box_height

        def draw_centered_text_overlay(draw_obj, text, font, y_pos, color=(255, 255, 255, 255)):
            bbox = draw_obj.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            x_pos = (width - text_width) // 2
            draw_obj.text((x_pos, y_pos), text, font=font, fill=color)

        draw_centered_text_overlay(draw_overlay, sub_text, font_sub, y0 + 35, color=(180, 180, 180, 255))

        # Force title into balanced rows, honoring explicit newlines if present
        def split_title_into_lines(text):
            if "\n" in text:
                return [line.strip() for line in text.split("\n")]
            if " : " in text:
                parts = text.split(" : ", 1)
                return [parts[0].strip(), parts[1].strip()]
            
            words = text.split()
            if len(words) <= 3:
                return [text]
            
            best_diff = float('inf')
            best_idx = 1
            for i in range(1, len(words)):
                part1 = " ".join(words[:i])
                part2 = " ".join(words[i:])
                diff = abs(len(part1) - len(part2))
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
            return [" ".join(words[:best_idx]), " ".join(words[best_idx:])]

        title_lines = split_title_into_lines(title_text)
        
        line_spacing = 10
        line_heights = []
        total_title_height = 0
        for line in title_lines:
            bbox = draw_overlay.textbbox((0, 0), line, font=font_title)
            h = bbox[3] - bbox[1]
            line_heights.append(h)
            total_title_height += h
        total_title_height += line_spacing * (len(title_lines) - 1)

        box_content_height = y1 - y0 - 120
        start_y = y0 + 80 + (box_content_height - total_title_height) // 2
        if start_y < y0 + 80:
            start_y = y0 + 80

        current_y = start_y
        for idx, line in enumerate(title_lines):
            draw_centered_text_overlay(draw_overlay, line, font_title, current_y, color=(255, 255, 255, 255))
            current_y += line_heights[idx] + line_spacing

        line_y = y1 - 35
        line_width = 120
        line_x_start = (width - line_width) // 2
        draw_overlay.line([(line_x_start, line_y), (line_x_start + line_width, line_y)], fill=(80, 80, 80, 255), width=2)

        # Save pure black canvas title card directly
        final_image = image.convert("RGB")
        final_image.save(temp_img_path)
        typer.echo(f"Saved dynamic title card overlay to {temp_img_path}")

        # 5. Probe the backup_path for video/audio specs and durations
        fps_str = "25"
        tb_den = "90000"
        ar_str = "48000"
        v_width = 1080
        v_height = 1080
        v_dur = None
        a_dur = None

        cmd_probe = [
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", backup_path
        ]
        probe_res = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if probe_res.returncode == 0:
            probe_data = json.loads(probe_res.stdout)
            for stream in probe_data.get("streams", []):
                codec_type = stream.get("codec_type")
                
                # Extract duration
                dur = stream.get("duration")
                if dur is None:
                    dur = stream.get("tags", {}).get("DURATION")
                dur_sec = None
                if dur is not None:
                    try:
                        if ":" in str(dur):
                            parts = str(dur).split(":")
                            dur_sec = float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
                        else:
                            dur_sec = float(dur)
                    except ValueError:
                        pass
                
                if codec_type == "video":
                     v_dur = dur_sec
                     v_width = int(stream.get("width") or 1080)
                     v_height = int(stream.get("height") or 1080)
                     avg_fps = stream.get("avg_frame_rate")
                     r_fps = stream.get("r_frame_rate")
                     fps_str = avg_fps if avg_fps and avg_fps != "0/0" else r_fps
                     if not fps_str or "/" not in fps_str:
                         fps_str = "25"
                     
                     tb_str = stream.get("time_base")
                     if tb_str and "/" in tb_str:
                         tb_den = tb_str.split("/")[1]
                     else:
                         tb_den = "90000"
                elif codec_type == "audio":
                     a_dur = dur_sec
                     ar_str = stream.get("sample_rate", "48000")
        else:
            typer.echo(f"Warning probing media specs via ffprobe. Using defaults.")

        # 6. Equalize master body durations in single-pass filtergraph (Audio is the master timeline ground truth)
        effective_a_dur = a_dur_fresh if a_dur_fresh is not None else a_dur
        body_v_extra_filter = ""
        if is_black_canvas:
            if os.path.exists(temp_remux_path):
                body_video_path = temp_remux_path
            else:
                body_video_path = master_path
        else:
            input_body_path = temp_remux_path if os.path.exists(temp_remux_path) else backup_path
            body_video_path = input_body_path
            if effective_a_dur is not None and (v_dur is None or abs(v_dur - effective_a_dur) > 0.05):
                target_dur = effective_a_dur
                if v_dur and v_dur < target_dur:
                    pad_dur = target_dur - v_dur
                    typer.echo(f"Extending Mosaic video stream with final frame pad ({pad_dur:.3f}s) in single-pass filtergraph...")
                    body_v_extra_filter = f",tpad=stop_mode=clone:stop_duration={pad_dur:.3f},trim=duration={target_dur:.3f},setpts=PTS-STARTPTS"
                else:
                    typer.echo(f"Trimming Mosaic video stream to {target_dur:.3f}s in single-pass filtergraph...")
                    body_v_extra_filter = f",trim=duration={target_dur:.3f},setpts=PTS-STARTPTS"

        # 7. Render intro
        intro_duration = 1.5
        typer.echo(f"Rendering {intro_duration}-second intro (FPS: {fps_str}, Sample Rate: {ar_str}Hz, Timescale: {tb_den})...")
        cmd_intro = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-r", fps_str,
            "-i", temp_img_path,
            "-i", music,
            "-filter_complex", f"[1:a]afade=t=out:st={intro_duration - 0.2:.3f}:d=0.2[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", ar_str,
            "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-video_track_timescale", tb_den,
            "-t", f"{intro_duration:.3f}",
            intro_video_path
        ]
        res_intro = subprocess.run(cmd_intro, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_intro.returncode != 0:
            typer.echo(f"Error rendering intro video: {res_intro.stderr}", err=True)
            raise typer.Exit(code=1)

        # 8. Concatenate with a 1-second crossfade
        os.makedirs(out_dir, exist_ok=True)
        out_filename = f"{base_name}.mp4"
        out_path = os.path.join(out_dir, out_filename)
        variant_filename = f"{episode}-{num}-{compile_source}.mp4"
        variant_path = os.path.join(out_dir, variant_filename)

        sorted_clips = sorted(plan_data, key=lambda x: x["num"])
        is_last_clip = (sorted_clips[-1]["num"] == num)

        temp_img_outro_path = f"temp_outro_img_{num}.png"
        temp_outro_video_path = f"temp_outro_{num}.mp4"
        temp_ass_path = f"temp_captions_{num}.ass"

        # Resolve duration of master body
        body_duration = 5.0
        if effective_a_dur is not None:
            body_duration = effective_a_dur
        else:
            try:
                dur_cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", body_video_path
                ]
                dur_res = subprocess.run(dur_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if dur_res.returncode == 0:
                    body_duration = float(dur_res.stdout.strip())
            except Exception:
                pass

        if not is_last_clip:
            typer.echo(f"Rendering 5-second outro transition card (curiosity question)...")
            
            # Resolve bridge_text
            bridge_text_input = clip.get("bridge_text", "")
            if isinstance(bridge_text_input, list):
                bridge_text = " ".join(bridge_text_input)
            else:
                bridge_text = str(bridge_text_input).strip()
            if not bridge_text:
                bridge_text = f"What is the deeper secret behind Part {num}?"

            # Generate outro image with semi-transparent charcoal banner
            img_outro = Image.new("RGBA", (v_width, v_height), color=(0, 0, 0, 255))
            draw_outro = ImageDraw.Draw(img_outro)
            
            font_path_outro = find_system_fonts()[0]
            try:
                font_outro = ImageFont.truetype(font_path_outro, 42)
            except Exception:
                font_outro = ImageFont.load_default()

            def wrap_text_outro(text, font, max_w):
                if "\n" in text:
                    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
                else:
                    raw_lines = [text]
                
                final_lines = []
                for r_line in raw_lines:
                    words = r_line.split()
                    curr = ""
                    for w in words:
                        test = f"{curr} {w}".strip()
                        bbox = draw_outro.textbbox((0, 0), test, font=font)
                        if (bbox[2] - bbox[0]) <= max_w:
                            curr = test
                        else:
                            if curr:
                                final_lines.append(curr)
                            curr = w
                    if curr:
                        final_lines.append(curr)
                return final_lines

            # Set max width to v_width - 240 (~500px) so text breaks into 2-4 balanced lines
            lines_outro = wrap_text_outro(bridge_text, font_outro, v_width - 240)
            line_spacing_outro = 14
            line_heights_outro = []
            total_h_outro = 0
            for line in lines_outro:
                bbox = draw_outro.textbbox((0, 0), line, font=font_outro)
                h = bbox[3] - bbox[1]
                line_heights_outro.append(h)
                total_h_outro += h
            total_h_outro += line_spacing_outro * (len(lines_outro) - 1)

            # Draw charcoal container box behind outro text
            box_w_outro = int(v_width * 0.88)
            box_h_outro = max(240, total_h_outro + 80)
            x0_out = (v_width - box_w_outro) // 2
            y0_out = (v_height - box_h_outro) // 2
            # Minimalist Pure Black & White: No grey box, pure white typography on pure #000000 black
            # (No rounded rectangle container)

            curr_y_outro = (v_height - total_h_outro) // 2
            for idx, line in enumerate(lines_outro):
                bbox = draw_outro.textbbox((0, 0), line, font=font_outro)
                w = bbox[2] - bbox[0]
                draw_outro.text(((v_width - w) // 2, curr_y_outro), line, font=font_outro, fill=(255, 255, 255, 255))
                curr_y_outro += line_heights_outro[idx] + line_spacing_outro

            # Subtle thin pure white divider rule
            rule_y = curr_y_outro + 25
            cx = v_width // 2
            draw_outro.line([(cx - 70, rule_y), (cx + 70, rule_y)], fill=(255, 255, 255, 180), width=2)

            img_outro.convert("RGB").save(temp_img_outro_path)

            start_time = max(0.0, body_duration - 5.0)

            # Generate outro card video
            cmd_outro = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-r", fps_str,
                "-i", temp_img_outro_path,
                "-ss", f"{start_time:.6f}",
                "-i", body_video_path,
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first,afade=t=out:st=0:d=5.0[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", ar_str,
                "-ac", "2",
                "-pix_fmt", "yuv420p",
                "-video_track_timescale", tb_den,
                "-t", "5.0",
                temp_outro_video_path
            ]
            res_out = subprocess.run(cmd_outro, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_out.returncode != 0:
                typer.echo(f"Warning generating outro card video: {res_out.stderr}")

        # 8. Generate ASS Captions & Prepare 1080x1920 Vertical Render Filter
        fonts_dir = ensure_dejavu_font()
        fresh_audio_for_caps = audio_matches[0] if audio_matches else None
        caption_chunks = generate_clip_captions(
            target_clip if target_clip is not None else clip,
            plan_file=plan_file,
            audio_path=fresh_audio_for_caps,
            intro_offset=intro_duration,
            body_duration=body_duration,
            has_outro=(not is_last_clip)
        )
        is_info_mode = (compile_source == "manim")
        write_ass_file(
            caption_chunks,
            temp_ass_path,
            body_duration=body_duration,
            intro_offset=intro_duration,
            visual_source=compile_source
        )
        os.makedirs("captions", exist_ok=True)
        write_ass_file(
            caption_chunks,
            os.path.join("captions", f"{base_name}.ass"),
            body_duration=body_duration,
            intro_offset=intro_duration,
            visual_source=compile_source
        )
        typer.echo(f"Prepared {len(caption_chunks)} ASS caption events (1080x1920 vertical spec) -> {temp_ass_path}")

        scale_filter = f"scale={v_width}:{v_height}:force_original_aspect_ratio=decrease,pad={v_width}:{v_height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25"
        body_v_filter = f"{scale_filter}{body_v_extra_filter},settb=1/90000"
        vertical_burn_filter = f"scale=740:740:force_original_aspect_ratio=decrease,pad=1080:1920:170:590:color=black,subtitles=filename={temp_ass_path}:fontsdir={fonts_dir},setsar=1"

        def build_concat_cmd(crf_val: int):
            if not is_last_clip and os.path.exists(temp_outro_video_path):
                return [
                    "ffmpeg", "-y",
                    "-i", intro_video_path,
                    "-i", body_video_path,
                    "-i", temp_outro_video_path,
                    "-filter_complex",
                    f"[0:v]{scale_filter},settb=1/90000[v0];"
                    f"[1:v]{body_v_filter}[v1];"
                    f"[2:v]{scale_filter},settb=1/90000[v2];"
                    "[v0][v1]concat=n=2:v=1:a=0[v01];"
                    "[v01]fps=25,settb=1/90000[v01tb];"
                    f"[v01tb][v2]xfade=transition=fade:duration=1.0:offset={intro_duration + body_duration - 1.0:.3f}[v740];"
                    f"[v740]{vertical_burn_filter}[v];"
                    "[0:a][1:a]concat=n=2:v=0:a=1[a0];"
                    "[a0][2:a]acrossfade=d=1.0:c1=tri:c2=tri[a]",
                    "-map", "[v]",
                    "-map", "[a]",
                    "-c:v", "libx264",
                    "-crf", str(crf_val),
                    "-preset", "veryfast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-movflags", "+faststart",
                    variant_path
                ]
            else:
                return [
                    "ffmpeg", "-y",
                    "-i", intro_video_path,
                    "-i", body_video_path,
                    "-filter_complex",
                    f"[0:v]{scale_filter},settb=1/90000[v0];"
                    f"[1:v]{body_v_filter}[v1];"
                    "[v0][v1]concat=n=2:v=1:a=0[v740];"
                    f"[v740]{vertical_burn_filter}[v];"
                    "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                    "-map", "[v]",
                    "-map", "[a]",
                    "-c:v", "libx264",
                    "-crf", str(crf_val),
                    "-preset", "veryfast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-movflags", "+faststart",
                    variant_path
                ]

        typer.echo(f"Compiling 1080x1920 vertical video with burned ASS captions into {variant_path}...")
        current_crf = 20
        res_concat = subprocess.run(build_concat_cmd(current_crf), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Enforce <= 20 MB Nostr free upload cap by raising CRF if needed
        max_bytes = 20 * 1024 * 1024
        while res_concat.returncode == 0 and os.path.exists(variant_path) and os.path.getsize(variant_path) > max_bytes and current_crf < 30:
            size_mb = os.path.getsize(variant_path) / (1024 * 1024)
            current_crf += 4
            typer.echo(f"Render size ({size_mb:.2f} MB) exceeds 20 MB cap; re-encoding with CRF {current_crf}...")
            res_concat = subprocess.run(build_concat_cmd(current_crf), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if res_concat.returncode == 0:
            typer.echo(f"Successfully compiled clip: {out_path}")
            
            # Sync compiled reel to Google Drive dd_hub/{mosaics,manims}/<episode>-<num>.mp4 for mobile review & manual uploads
            try:
                hub_root = os.environ.get("DD_HUB_ROOT", r"G:\My Drive\dd_hub")
                if os.path.exists(hub_root) and episode:
                    hub_reel_folder = "manims" if compile_source == "manim" else "mosaics"
                    hub_dest_dir = os.path.join(hub_root, hub_reel_folder)
                    os.makedirs(hub_dest_dir, exist_ok=True)
                    hub_dest_file = os.path.join(hub_dest_dir, out_filename)
                    shutil.copy2(variant_path, hub_dest_file)
                    typer.echo(f"Synced {compile_source} reel to dd_hub/{hub_reel_folder} -> {hub_dest_file}")
            except Exception as hub_e:
                typer.echo(f"Warning syncing to dd_hub: {hub_e}")

            # Safeguard: If active master, update master out_path and sync to deepDive
            is_active_master = (compile_source == active_master_src)
            if is_active_master:
                try:
                    shutil.copy2(variant_path, out_path)
                except Exception:
                    pass
                if episode:
                    deepdive_clips_dir = os.path.abspath(os.path.join("..", "deepDive", "src", "ddma", "docs", "episodes", str(episode), "clips"))
                    if os.path.exists(os.path.dirname(deepdive_clips_dir)):
                        os.makedirs(deepdive_clips_dir, exist_ok=True)
                        dest_file = os.path.join(deepdive_clips_dir, out_filename)
                        try:
                            shutil.copy2(variant_path, dest_file)
                            typer.echo(f"Synced ACTIVE MASTER ({compile_source}) to deepDive publication repo -> {dest_file}")
                        except Exception as e:
                            typer.echo(f"Warning: Could not sync to deepDive clips: {e}")
            else:
                typer.echo(f"[SAFEGUARD] Compiled '{compile_source}' preview to {variant_path}.")
                typer.echo(f"[SAFEGUARD] deepDive publication repo was NOT modified (active master is locked to '{active_master_src}').")
            
            # Verification checklist (1080x1920 DAR 9:16, <=180s, <=20MB, |rendered_duration - mp4 duration| <= 2s) and reconcile plan.json
            try:
                cmd_verify = [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,display_aspect_ratio:format=duration,size",
                    "-of", "json", variant_path
                ]
                ver_res = subprocess.run(cmd_verify, stdout=subprocess.PIPE, text=True)
                if ver_res.returncode == 0:
                    ver_data = json.loads(ver_res.stdout)
                    v_stream = (ver_data.get("streams") or [{}])[0]
                    v_fmt = ver_data.get("format") or {}
                    final_dur = round(float(v_fmt.get("duration", 0.0)), 2)
                    final_size_mb = round(float(v_fmt.get("size", os.path.getsize(variant_path))) / (1024 * 1024), 2)
                    out_w = int(v_stream.get("width", 0))
                    out_h = int(v_stream.get("height", 0))
                    out_dar = v_stream.get("display_aspect_ratio", "")

                    typer.echo(
                        f"[OK] VERIFIED: {out_w}x{out_h} (DAR {out_dar}) | "
                        f"Duration: {final_dur:.2f}s (<=180s) | Size: {final_size_mb:.2f} MB (<=20MB) | "
                        f"Captions: {len(caption_chunks)} events"
                    )
                    if final_dur > 180.0:
                        typer.echo(f"\n[WARNING] Final compiled clip duration ({final_dur:.2f}s) exceeds the 180s YouTube Shorts ceiling!")

                    # Forward reconciliation: record rendered media properties without corrupting source coordinates
                    if target_clip is not None:
                        import hashlib
                        target_clip["rendered_duration"] = final_dur
                        target_clip["duration"] = final_dur
                        target_clip["audio_duration"] = round(float(body_duration), 2)
                        target_clip["intro_offset"] = intro_duration
                        target_clip["outro_duration"] = 5.0 if not is_last_clip else 0.0
                        if "source_start" not in target_clip and "start" in target_clip:
                            target_clip["source_start"] = target_clip["start"]
                        if "source_end" not in target_clip and "end" in target_clip:
                            target_clip["source_end"] = target_clip["end"]
                        
                        audio_sig = hashlib.md5(json.dumps(target_clip.get("segments", []), sort_keys=True).encode("utf-8")).hexdigest()
                        compile_sig = hashlib.md5(json.dumps({
                            "title": target_clip.get("title", ""),
                            "ep_title": ep_title,
                            "bridge_text": target_clip.get("bridge_text", ""),
                            "mosaic_run_id": mosaic_run_id,
                            "visual_source": target_clip.get("visual_source", ""),
                            "infographic_scenes": target_clip.get("infographic_scenes", []),
                            "segments": target_clip.get("segments", []),
                            "force_draft": force_draft,
                            "text": target_clip.get("text", ""),
                            "caption_chunks": target_clip.get("caption_chunks", []),
                            "vertical_format": "1080x1920_ass_v1"
                        }, sort_keys=True).encode("utf-8")).hexdigest()
                        target_clip["_audio_sig"] = audio_sig
                        target_clip["_compiled_sig"] = compile_sig

                        # Save updated plan.json to plan_file atomically
                        try:
                            with open(plan_file, "w", encoding="utf-8") as pf:
                                json.dump(plan_data, pf, indent=4)
                            if os.path.abspath(plan_file) != os.path.abspath("plan.json"):
                                with open("plan.json", "w", encoding="utf-8") as rpf:
                                    json.dump(plan_data, rpf, indent=4)
                            typer.echo(f"Reconciled plan metadata for Clip {num}: rendered_duration={final_dur}s, audio_duration={round(float(body_duration), 2)}s, intro_offset={intro_duration}s")
                            
                            # Sync to docs/episodes/<ep>/plan.json if exists
                            ep_val = ep_prefix if ep_prefix else episode
                            if ep_val:
                                docs_ep_plan = os.path.join("docs", "episodes", ep_val, "plan.json")
                                if os.path.exists(os.path.dirname(docs_ep_plan)):
                                    with open(docs_ep_plan, "w", encoding="utf-8") as dpf:
                                        json.dump(plan_data, dpf, indent=4)
                        except Exception as ex_save:
                            typer.echo(f"Warning: Failed to save reconciled plan metadata: {ex_save}")
            except Exception as ex_ver:
                typer.echo(f"Warning during post-compile verification: {ex_ver}")
        else:
            typer.echo(f"Error concatenating: {res_concat.stderr}", err=True)
            raise typer.Exit(code=1)

    finally:
        # Clean up temp files
        temp_files_to_remove = [
            temp_img_path, intro_video_path, concat_txt_path, temp_body_path, 
            temp_extracted_frame, temp_img_outro_path, temp_outro_video_path,
            temp_remux_path, temp_ass_path
        ]
        for temp_f in temp_files_to_remove:
            if os.path.exists(temp_f):
                try:
                    os.remove(temp_f)
                except Exception:
                    pass


def update_ingestion_progress(proj_dir, stage_index, percent, action_text, log_line=None):
    progress_file = os.path.join(proj_dir, "ingestion_progress.json")
    
    stages = [
        {"index": 1, "name": "Transcription", "icon": "🎙️", "label": "Transcribing Raw Audio"},
        {"index": 2, "name": "Storyboarding", "icon": "🧠", "label": "Structuring Clip Boundaries & Bridges"},
        {"index": 3, "name": "Workspace Sync", "icon": "🚀", "label": "Registering Episode Manifest"}
    ]
    
    existing_logs = []
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                existing_logs = prev_data.get("logs", [])
        except Exception:
            pass
            
    if log_line:
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        existing_logs.append(f"[{timestamp}] {log_line}")
        if len(existing_logs) > 100:
            existing_logs = existing_logs[-100:]

    data = {
        "status": "ingesting" if percent < 100 else "ready",
        "current_stage": stage_index,
        "percent": min(100, max(0, int(percent))),
        "action_text": action_text,
        "stages": stages,
        "logs": existing_logs
    }
    
    try:
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


@app.command()
def snap_quote_to_words(quote, words, search_start_sec=0.0):
    """
    Search Whisper word list for matching quote text and return exact (start_sec, end_sec).
    """
    if not words or not quote:
        return None, None
    
    clean_quote = re.sub(r'[^\w\s]', '', str(quote).lower()).strip()
    quote_tokens = clean_quote.split()
    if not quote_tokens:
        return None, None

    transcript_tokens = [re.sub(r'[^\w]', '', w.get("word", "").lower().strip()) for w in words]
    first_token = quote_tokens[0]
    
    for idx, w in enumerate(words):
        if w.get("start", 0) < search_start_sec - 10.0:
            continue
        if transcript_tokens[idx] == first_token:
            match_count = 0
            for j in range(len(quote_tokens)):
                if idx + j < len(transcript_tokens) and transcript_tokens[idx + j] == quote_tokens[j]:
                    match_count += 1
                else:
                    break
            if match_count >= min(2, len(quote_tokens)):
                s_time = round(words[idx]["start"], 3)
                e_idx = min(idx + len(quote_tokens) - 1, len(words) - 1)
                e_time = round(words[e_idx]["end"], 3)
                return s_time, e_time

    return None, None

@app.command("ingest-episode")
def ingest_episode(
    audio: str = typer.Option(..., help="Path to input audio file"),
    episode: int = typer.Option(..., help="Episode number (e.g. 246)"),
    title: str = typer.Option(..., help="Episode title"),
    num_clips: int = typer.Option(18, help="Number of structural clips to divide into (default 18)"),
    mode: str = typer.Option("tripartite", help="Ingestion mode: 'structured' (fast uniform sentence snapping) or 'unstructured' (Gemini AI topic discovery)")
):
    """
    Automated end-to-end ingestion pipeline: project setup, transcription, plan generation,
    sample-accurate slicing with EBU R128 normalization, draft muxing, clip compilation, and docs sync.
    """
    if hasattr(audio, 'default'): audio = str(audio.default)
    if hasattr(episode, 'default'): episode = int(episode.default)
    if hasattr(title, 'default'): title = str(title.default)
    if hasattr(num_clips, 'default'): num_clips = int(num_clips.default)
    if hasattr(mode, 'default'): mode = str(mode.default)

    proj_id = f"episode_{episode}"
    proj_dir = os.path.join("projects", proj_id)
    os.makedirs(proj_dir, exist_ok=True)

    update_ingestion_progress(proj_dir, 1, 10, "Initializing workspace and copying source audio...", f"Started ingestion pipeline for Episode {episode}: {title} (Mode: {mode})")

    ext = os.path.splitext(audio)[1]
    audio_dest_name = f"{episode}{ext}"
    audio_dest_path = os.path.join(proj_dir, audio_dest_name)
    if not os.path.exists(audio_dest_path) and os.path.exists(audio):
        shutil.copy2(audio, audio_dest_path)

    # 1. Save project_info.json
    info_data = {
        "id": proj_id,
        "name": f"Episode {episode}",
        "title": title,
        "audio_filename": audio_dest_name,
        "audio_file": audio_dest_name,
        "status": "ingesting"
    }
    with open(os.path.join(proj_dir, "project_info.json"), "w", encoding="utf-8") as f:
        json.dump(info_data, f, indent=2)

    # 2. Transcribe
    trans_path = os.path.join(proj_dir, "transcription.json")
    if not os.path.exists(trans_path):
        update_ingestion_progress(proj_dir, 1, 30, f"Transcribing {audio_dest_name} via faster-whisper...", "Running faster-whisper transcription with word timestamps (large-v3-turbo)...")
        typer.echo(f"Transcribing {audio_dest_path} with faster-whisper (large-v3-turbo)...")
        transcribe(audio=audio_dest_path, model_name="large-v3-turbo", out=trans_path, word_timestamps=True)
        if os.path.exists("transcription.json") and not os.path.exists(trans_path):
            shutil.copy2("transcription.json", trans_path)

    update_ingestion_progress(proj_dir, 2, 50, "Whisper transcription ready. Analyzing structural timestamps...", "Transcription complete with word-level timestamps.")

    # 3. Generate Plan
    plan_path = os.path.join(proj_dir, "plan.json")
    clips_list = []
    if os.path.exists(trans_path):
        update_ingestion_progress(proj_dir, 2, 70, f"Structuring audio into {num_clips} ~2-minute topic clips...", f"Dividing timeline into {num_clips} structural segments.")
        typer.echo(f"Generating structural plan with {num_clips} clips...")
        with open(trans_path, "r", encoding="utf-8") as tf:
            t_data = json.load(tf)
        if mode == "tripartite":
            typer.echo(f"Casting NotebookLM tripartite audio with Gemini and snapping Whisper word timestamps...")
            clips_list = cast_tripartite_plan_with_gemini(t_data, num_clips=num_clips, default_visual_source="mosaic", audio_path=audio_dest_path)
            if clips_list and clips_list[0].get("num") == 0 and title and not title.lower().startswith("episode"):
                clips_list[0]["title"] = title
        if not clips_list:
            words = []
            for seg in t_data.get("segments", []):
                words.extend(seg.get("words", []))
            total_dur = words[-1]["end"] if words else 0
            target_dur = total_dur / max(1, num_clips)

            curr_start = 0
            for i in range(num_clips):
                target_end = (i + 1) * target_dur
                if i == num_clips - 1:
                    end_idx = len(words) - 1
                else:
                    best_idx = curr_start
                    min_diff = 999999
                    for idx in range(curr_start + 15, len(words) - 10):
                        w = words[idx]
                        diff = abs(w["end"] - target_end)
                        text = w.get("word", "").strip()
                        if text.endswith(".") or text.endswith("?") or text.endswith("!"):
                            diff -= 10.0
                        if diff < min_diff:
                            min_diff = diff
                            best_idx = idx
                    end_idx = best_idx
                
                s_time = round(words[curr_start]["start"], 3)
                e_time = round(words[end_idx]["end"], 3)
                c_num = i + 1

                c_obj = build_rough_cut_segments(c_num, s_time, e_time, t_data.get("segments", []), num_clips)
                clips_list.append(c_obj)
                curr_start = end_idx + 1
                if curr_start >= len(words):
                    break

            # Pass 2 (for fallback rough cuts only): Concise <= 5-word Outro Bridge Questions based on NEXT clip's title!
            for i in range(len(clips_list) - 1):
                curr_c = clips_list[i]
                next_c = clips_list[i + 1]
                next_title = " ".join(next_c.get("title", f"Part {next_c.get('num', i+2)}").split()[:3])
                curr_c["bridge_text"] = [f"What Is {next_title} ?"]

        with open(plan_path, "w", encoding="utf-8") as pf:
            json.dump(clips_list, pf, indent=2)

    update_ingestion_progress(proj_dir, 3, 85, f"Generated plan.json with {len(clips_list)} clips. Syncing workspace...", f"Created storyboard plan with {len(clips_list)} clips.")

    # 4. Sync plan.json to snapshot, root, and docs
    snapshot_path = os.path.join(proj_dir, "plan_snapshot.json")
    shutil.copy2(plan_path, snapshot_path)
    shutil.copy2(plan_path, "plan.json")
    docs_ep_dir = os.path.join("docs", "episodes", str(episode))
    os.makedirs(docs_ep_dir, exist_ok=True)
    shutil.copy2(plan_path, os.path.join(docs_ep_dir, "plan.json"))

    # 5. Register in docs/episodes.json
    update_ingestion_progress(proj_dir, 3, 95, "Syncing episode manifest and preview player assets...", "Updating docs/episodes.json for GitHub Pages routing.")
    ep_manifest_path = os.path.join("docs", "episodes.json")
    if os.path.exists(ep_manifest_path):
        try:
            with open(ep_manifest_path, "r", encoding="utf-8") as mf:
                manifest = json.load(mf)
            
            manifest = [m for m in manifest if str(m.get("id")) != str(episode) and str(m.get("number")) != str(episode)]
            for m in manifest:
                m["isDefault"] = False

            ep_title = title
            if clips_list and len(clips_list) > 0 and clips_list[0].get("title"):
                ep_title = clips_list[0]["title"]

            manifest.append({
                "id": str(episode),
                "number": episode,
                "title": ep_title,
                "fullTitle": f"Episode {episode}: {ep_title}",
                "planPath": f"episodes/{episode}/plan.json",
                "clipsDir": f"episodes/{episode}/clips",
                "links": {},
                "isDefault": True
            })
            with open(ep_manifest_path, "w", encoding="utf-8") as mf:
                json.dump(manifest, mf, indent=2)
        except Exception as me:
            typer.echo(f"Warning updating episodes.json: {me}")

    # Mark ready
    info_data["status"] = "ready"
    with open(os.path.join(proj_dir, "project_info.json"), "w", encoding="utf-8") as f:
        json.dump(info_data, f, indent=2)

    update_ingestion_progress(proj_dir, 3, 100, "Episode ingestion complete! Project ready in Curator.", f"Episode {episode} instant ingestion pipeline completed successfully.")
    typer.echo(f"[SUCCESS] Episode {episode} instant ingestion pipeline complete! Project ready in Curator & Preview Player.")


if __name__ == "__main__":
    app()


@app.command("cast-tripartite")
def cast_tripartite_cmd(
    transcription: str = typer.Option("transcription.json", help="Path to Whisper transcription JSON"),
    num_clips: Optional[int] = typer.Option(None, help="Optional number of clips to structure"),
    out: str = typer.Option("plan.json", help="Path to save generated tripartite plan JSON"),
    source: str = typer.Option("mosaic", help="Default active visual master ('mosaic' or 'manim')")
):
    """
    Automated zero-trim plan generator for NotebookLM tripartite audio:
    Discovers Punchline Hook, Deliberation, and Outro Teaser boundaries via Gemini,
    casts Intro/Outro Cards, and snaps word timestamps via Whisper.
    """
    if not os.path.exists(transcription):
        typer.echo(f"Error: Transcription {transcription} not found.", err=True)
        return
    with open(transcription, "r", encoding="utf-8") as f:
        t_data = json.load(f)

    clips = cast_tripartite_plan_with_gemini(t_data, num_clips=num_clips, default_visual_source=source)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(clips, f, indent=2)
    typer.echo(f"Successfully cast {len(clips)} tripartite clips saved to {out}!")
