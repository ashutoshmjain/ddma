import typer
import whisper
import json
import os
import re
import subprocess
import time
import shutil
from typing import Optional

app = typer.Typer(help="DeepDive Media Automator (DDMA) CLI Tool")

@app.command()
def transcribe(
    audio: str = typer.Option(..., help="Path to input audio file"),
    model_name: str = typer.Option("tiny.en", help="Whisper model name to use"),
    out: str = typer.Option("transcription.json", help="Path to save transcription JSON"),
    word_timestamps: bool = typer.Option(True, help="Enable word-level timestamps")
):
    """
    Transcribe the audio file using Whisper and cache the JSON output.
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

    typer.echo(f"Loading Whisper model '{model_name}'...")
    start_time = time.time()
    model = whisper.load_model(model_name)
    typer.echo(f"Model loaded in {time.time() - start_time:.2f} seconds.")

    typer.echo(f"Transcribing {audio} (word_timestamps={word_timestamps})...")
    transcribe_start = time.time()
    result = model.transcribe(audio, verbose=False, word_timestamps=word_timestamps)
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
    Builds a 5-part Rough-Cut Plan segment structure for a clip:
    1. Intro Music Sting (deepDive-soft-ok.mp3 for clip 1 & 2; sting for clip 3+)
    2. Punchline / Hook Audio Segment (extracted 15-25s quote from transcript within window)
    3. Music Transition Sting (4.5s sting with 0.3s crossfade)
    4. Main Body Audio Segment (the main timeline range)
    5. Curiosity Bridge Question (text question in bridge_text)
    """
    in_window = [s for s in segments if s.get("start", 0) >= start_time and s.get("end", 0) <= end_time + 1.0]
    
    if clip_num in [1, 2]:
        intro_music = "deepDive-soft-ok.mp3"
    else:
        stings = [
            "Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3",
            "Howling (Sting) - Gunnar Olsen.mp3",
            "Demilitarized Zone (Sting) - Ethan Meixsell.mp3",
            "Double Helix (Sting) - Ethan Meixsell.mp3"
        ]
        intro_music = stings[(clip_num - 1) % len(stings)]

    hook_segment = None
    if in_window:
        for seg in reversed(in_window):
            seg_dur = seg.get("end", 0) - seg.get("start", 0)
            if 10.0 <= seg_dur <= 30.0:
                hook_segment = {
                    "type": "audio",
                    "start": round(seg.get("start"), 2),
                    "end": round(seg.get("end"), 2),
                    "duration": round(seg_dur, 2),
                    "text": seg.get("text", "").strip()
                }
                break

    if not hook_segment and in_window:
        first_seg = in_window[0]
        hook_segment = {
            "type": "audio",
            "start": round(first_seg.get("start"), 2),
            "end": round(min(first_seg.get("start") + 15.0, end_time), 2),
            "duration": round(min(15.0, end_time - first_seg.get("start")), 2),
            "text": first_seg.get("text", "").strip()
        }

    mid_music = "Howling (Sting) - Gunnar Olsen.mp3"
    main_text = " ".join([s.get("text", "").strip() for s in in_window]).strip()

    seg_list = [
        {
            "type": "music",
            "music_file": intro_music,
            "duration": 4.5,
            "crossfade": 0,
            "volume": 1.0
        }
    ]
    if hook_segment:
        seg_list.append(hook_segment)
        seg_list.append({
            "type": "music",
            "music_file": mid_music,
            "duration": 4.5,
            "crossfade": 0.3
        })

    seg_list.append({
        "type": "audio",
        "start": round(start_time, 2),
        "end": round(end_time, 2),
        "duration": round(end_time - start_time, 2),
        "text": main_text
    })

    bridge_question = f"What is the deeper secret behind Part {clip_num}?"
    if clip_num < total_clips:
        bridge_question = f"What happens when intelligence expands in Part {clip_num + 1}?"

    return {
        "num": clip_num,
        "title": f"Episode 245 Part {clip_num}" if clip_num > 1 else "Episode 245",
        "start": round(start_time, 2),
        "end": round(end_time, 2),
        "duration": round(end_time - start_time, 2),
        "bridge_text": [bridge_question],
        "segments": seg_list,
        "locked": True
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

            if target_b == total_duration:
                break

            t_curr = target_b
            clip_num += 1

            if target_b == total_duration:
                break

            t_curr = target_b
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
    out_dir: str = typer.Option(".", help="Output directory for clips")
):
    """
    Cut audio file into clips based on the plan using sample-accurate re-encoding.
    """
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
    typer.echo(f"Splitting {audio} into {len(plan_data)} clips...")

    for c in plan_data:
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

        start_str = to_time_str(c["start"])
        end_str = to_time_str(c["end"])

        segments = c.get("segments", [])
        has_music_seg = any(s.get("type") == "music" for s in segments)

        if has_music_seg and len(segments) > 0:
            typer.echo(f"Processing Clip {c['num']} with {len(segments)} segments (including music stings)...")
            temp_seg_files = []
            for s_idx, seg in enumerate(segments):
                t_seg = os.path.join(out_dir, f"temp_seg_{c['num']}_{s_idx}.wav")
                temp_seg_files.append(t_seg)
                if seg.get("type") == "music":
                    m_file = os.path.basename(seg.get("music_file", "deepDive-soft-ok.mp3"))
                    m_dur = seg.get("duration", 5.0)
                    m_vol = seg.get("volume", 1.0)
                    m_path = os.path.join("music", m_file)
                    if not os.path.exists(m_path):
                        m_path = os.path.join("music", "deepDive-soft-ok.mp3")
                    
                    cmd_m = [
                        "ffmpeg", "-y",
                        "-i", m_path,
                        "-t", str(m_dur),
                        "-ar", "48000", "-ac", "2",
                        "-af", f"volume={m_vol}",
                        t_seg
                    ]
                    res_m = subprocess.run(cmd_m, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res_m.returncode != 0:
                        typer.echo(f"Warning rendering music segment {s_idx} for clip {c['num']}: {res_m.stderr}", err=True)
                else:
                    s_start = to_time_str(seg.get("start", c["start"]))
                    s_end = to_time_str(seg.get("end", c["end"]))
                    s_vol = seg.get("volume", 1.0)
                    cmd_a = [
                        "ffmpeg", "-y",
                        "-ss", s_start,
                        "-to", s_end,
                        "-i", audio,
                        "-ar", "48000", "-ac", "2",
                        "-af", f"volume={s_vol}",
                        t_seg
                    ]
                    res_a = subprocess.run(cmd_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res_a.returncode != 0:
                        typer.echo(f"Warning rendering audio segment {s_idx} for clip {c['num']}: {res_a.stderr}", err=True)
            
            # Combine segment files
            temp_concat_wav = os.path.join(out_dir, f"temp_concat_{c['num']}.wav")
            cmd_cat = ["ffmpeg", "-y"]
            valid_seg_files = [tf for tf in temp_seg_files if os.path.exists(tf) and os.path.getsize(tf) > 0]
            if not valid_seg_files:
                typer.echo(f"Error: No valid segment audio files created for clip {c['num']}", err=True)
                continue

            for tf in valid_seg_files:
                cmd_cat += ["-i", tf]
            filter_complex = "".join(f"[{i}:a]" for i in range(len(valid_seg_files)))
            filter_complex += f"concat=n={len(valid_seg_files)}:v=0:a=1[out]"
            cmd_cat += ["-filter_complex", filter_complex, "-map", "[out]", temp_concat_wav]
            subprocess.run(cmd_cat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # EBU R128 Loudness Normalization to final MP3
            cmd_norm = [
                "ffmpeg", "-y",
                "-i", temp_concat_wav,
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:a", "libmp3lame", "-q:a", "2",
                out_path
            ]
            subprocess.run(cmd_norm, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Clean temp segment files
            for tf in temp_seg_files + [temp_concat_wav]:
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except Exception:
                        pass
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", audio,
                "-ss", start_str,
                "-to", end_str,
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
    
    audio_path = audio_files[0]
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    episode = ep_prefix if ep_prefix else base_name.split("-")[0]

    os.makedirs(out_dir, exist_ok=True)
    out_filename = f"{episode}-{num}.mp4"
    out_path = os.path.join(out_dir, out_filename)

    typer.echo(f"Found audio: {audio_path}")
    typer.echo(f"Muxing into black square draft: {out_path}...")

    # Mux using FFmpeg color source filter to generate a 740x740 black video dynamically
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "color=c=black:s=740x740:r=25",
        "-i", audio_path,
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
    force_draft: bool = typer.Option(False, help="Force black canvas draft body compilation even if Mosaic video exists")
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
            "music/deepDive-strong.mp3",
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
        mux_clip(num=num, plan_file=plan_file, master_dir=master_dir, out_dir=out_dir)
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

    # 3. Back up original master clip if needed
    if backup:
        if not os.path.exists(backup_path):
            typer.echo(f"Creating backup of original clip to {backup_path}...")
            shutil.copy2(master_path, backup_path)
        else:
            typer.echo(f"Backup already exists at {backup_path}")
    else:
        backup_path = master_path

    # Check for freshly cut audio clip (e.g. clips/245-1-*.mp3) and remux audio track
    audio_pattern1 = os.path.join(master_dir, f"{episode}-{num}-*.mp3")
    audio_pattern2 = os.path.join(master_dir, f"{episode}-{num}.mp3")
    audio_matches = glob.glob(audio_pattern1) + glob.glob(audio_pattern2)
    if not audio_matches:
        audio_matches = glob.glob(os.path.join(master_dir, f"*-{num}-*.mp3")) + glob.glob(os.path.join(master_dir, f"*-{num}.mp3"))
    
    if audio_matches and os.path.exists(backup_path):
        audio_matches.sort(key=os.path.getmtime, reverse=True)
        fresh_audio_path = audio_matches[0]
        typer.echo(f"Updating master body audio from fresh audio clip: {fresh_audio_path}...")
        
        # Probe fresh audio duration and master video duration
        a_dur_fresh = None
        v_dur_master = None
        fps_str = "30"
        try:
            p_a = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", fresh_audio_path], capture_output=True, text=True)
            if p_a.returncode == 0:
                a_dur_fresh = float(p_a.stdout.strip())
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

        temp_remux_path = f"temp_remux_{num}.mp4"
        target_clip = next((c for c in plan_data if c.get("num") == num), None)
        has_mosaic_id = bool(target_clip and target_clip.get("mosaic_run_id"))
        
        # A clip is a black canvas draft if force_draft is requested OR if it has never been rendered by Mosaic
        is_black_canvas = force_draft or not has_mosaic_id

        if is_black_canvas:
            typer.echo(f"Generating clean draft body video ({a_dur_fresh:.2f}s) from fresh audio clip...")
            cmd_remux = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s=740x740:r={fps_str}:d={a_dur_fresh:.3f}",
                "-i", fresh_audio_path,
                "-r", fps_str,
                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-t", f"{a_dur_fresh:.3f}",
                temp_remux_path
            ]
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
            if is_black_canvas and has_mosaic_id:
                typer.echo(f"Draft baseline body created at {temp_remux_path} (Mosaic master preserved at {backup_path}).")
            else:
                shutil.move(temp_remux_path, backup_path)
                typer.echo(f"Successfully updated master body audio track: {backup_path}")
        else:
            if os.path.exists(temp_remux_path):
                try:
                    os.remove(temp_remux_path)
                except Exception:
                    pass

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
        width, height = 740, 740
        bg_color = (18, 18, 18)
        image = Image.new("RGBA", (width, height), bg_color)

        draw_overlay = ImageDraw.Draw(image)

        # Resolve fonts
        font_path_reg, font_path_bold = find_system_fonts()
        if font_path and os.path.exists(font_path):
            font_path_reg = font_path
            font_path_bold = font_path

        try:
            if font_path_reg and font_path_bold:
                font_sub = ImageFont.truetype(font_path_reg, 24)
                font_title = ImageFont.truetype(font_path_bold, 40)
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

        sub_text = f"EPISODE {episode}" if num == 1 else f"EPISODE {episode} • PART {num}"
        title_text = title if title else f"Part {num}"

        # Create overlay layer for semi-transparent charcoal banner
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        # Centered charcoal banner
        box_width = int(width * 0.85)
        box_height = 280
        x0 = (width - box_width) // 2
        y0 = height // 2 - 160
        x1 = x0 + box_width
        y1 = y0 + box_height

        draw_overlay.rounded_rectangle([(x0, y0), (x1, y1)], radius=15, fill=(18, 18, 18, 200))

        def draw_centered_text_overlay(draw_obj, text, font, y_pos, color=(255, 255, 255, 255)):
            bbox = draw_obj.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            x_pos = (width - text_width) // 2
            draw_obj.text((x_pos, y_pos), text, font=font, fill=color)

        draw_centered_text_overlay(draw_overlay, sub_text, font_sub, y0 + 35, color=(150, 150, 150, 255))

        # Force title into balanced rows, honoring explicit newlines if present
        def split_title_into_lines(text):
            if "\n" in text:
                return [line.strip() for line in text.split("\n")]
            if " : " in text:
                parts = text.split(" : ", 1)
                return [parts[0].strip(), parts[1].strip()]
            
            words = text.split()
            if len(words) <= 1:
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

        # Composite the overlay onto the frame
        final_image = Image.alpha_composite(image, overlay).convert("RGB")
        final_image.save(temp_img_path)
        typer.echo(f"Saved dynamic title card overlay to {temp_img_path}")

        # 5. Probe the backup_path for video/audio specs and durations
        fps_str = "25"
        tb_den = "90000"
        ar_str = "48000"
        v_width = 740
        v_height = 740
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
                     v_width = int(stream.get("width") or 740)
                     v_height = int(stream.get("height") or 740)
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

        # 6. Equalize master body durations (Audio is the master timeline ground truth)
        if is_black_canvas and has_mosaic_id and os.path.exists(temp_remux_path):
            body_video_path = temp_remux_path
        else:
            body_video_path = backup_path
            temp_body_path = f"temp_body_{num}.mp4"
            if a_dur is not None and (v_dur is None or abs(v_dur - a_dur) > 0.05):
                target_dur = a_dur
                typer.echo(f"Equalizing master body stream durations to match audio ground truth ({a_dur:.3f}s)...")
                if v_dur and v_dur < a_dur:
                    # Video is shorter than audio: extend black canvas video stream to match audio duration exactly
                    cmd_norm = [
                        "ffmpeg", "-y",
                        "-f", "lavfi", "-i", f"color=c=black:s={v_width}x{v_height}:r=25:d={target_dur:.3f}",
                        "-i", backup_path,
                        "-map", "0:v",
                        "-map", "1:a",
                        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        "-ar", ar_str,
                        "-t", f"{target_dur:.3f}",
                        temp_body_path
                    ]
                else:
                    # Trim video stream down to match audio duration
                    cmd_norm = [
                        "ffmpeg", "-y",
                        "-i", backup_path,
                        "-ss", "0",
                        "-t", f"{target_dur:.3f}",
                        "-c:v", "libx264",
                        "-crf", "18",
                        "-preset", "fast",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-ar", ar_str,
                        temp_body_path
                    ]
                res_norm = subprocess.run(cmd_norm, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res_norm.returncode == 0:
                    body_video_path = temp_body_path
                    typer.echo(f"Master body successfully equalized to {target_dur:.3f}s.")
                else:
                    typer.echo(f"Warning: Failed to equalize master body, using original backup path. Error: {res_norm.stderr}")

        # 7. Render intro
        typer.echo(f"Rendering 2-second intro (FPS: {fps_str}, Sample Rate: {ar_str}Hz, Timescale: {tb_den})...")
        cmd_intro = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-r", fps_str,
            "-i", temp_img_path,
            "-i", music,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", ar_str,
            "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-video_track_timescale", tb_den,
            "-t", "2.0",
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

        sorted_clips = sorted(plan_data, key=lambda x: x["num"])
        is_last_clip = (sorted_clips[-1]["num"] == num)

        temp_img_outro_path = f"temp_outro_img_{num}.png"
        temp_outro_video_path = f"temp_outro_{num}.mp4"
        body_duration = 5.0

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

            # Generate outro image
            img_outro = Image.new("RGB", (v_width, v_height), color=(0, 0, 0))
            draw_outro = ImageDraw.Draw(img_outro)
            
            font_path_outro = find_system_fonts()[0]
            try:
                font_outro = ImageFont.truetype(font_path_outro, 34)
            except Exception:
                font_outro = ImageFont.load_default()

            def wrap_text_outro(text, font, max_w):
                words = text.split()
                lines = []
                curr = ""
                for w in words:
                    test = f"{curr} {w}".strip()
                    bbox = draw_outro.textbbox((0, 0), test, font=font)
                    if (bbox[2] - bbox[0]) <= max_w:
                        curr = test
                    else:
                        if curr:
                            lines.append(curr)
                        curr = w
                if curr:
                    lines.append(curr)
                return lines

            lines_outro = wrap_text_outro(bridge_text, font_outro, v_width - 160)
            line_spacing_outro = 18
            line_heights_outro = []
            total_h_outro = 0
            for line in lines_outro:
                bbox = draw_outro.textbbox((0, 0), line, font=font_outro)
                h = bbox[3] - bbox[1]
                line_heights_outro.append(h)
                total_h_outro += h
            total_h_outro += line_spacing_outro * (len(lines_outro) - 1)

            curr_y_outro = (v_height - total_h_outro) // 2
            for idx, line in enumerate(lines_outro):
                bbox = draw_outro.textbbox((0, 0), line, font=font_outro)
                w = bbox[2] - bbox[0]
                draw_outro.text(((v_width - w) // 2, curr_y_outro), line, font=font_outro, fill=(255, 255, 255))
                curr_y_outro += line_heights_outro[idx] + line_spacing_outro

            img_outro.save(temp_img_outro_path)

            # Probe duration of equalized master body to slice end audio
            try:
                dur_cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", body_video_path
                ]
                dur_res = subprocess.run(dur_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if dur_res.returncode == 0:
                    body_duration = float(dur_res.stdout.strip())
            except:
                pass
            start_time = max(0.0, body_duration - 5.0)

            # Generate outro card video
            cmd_outro = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-r", fps_str,
                "-i", temp_img_outro_path,
                "-ss", f"{start_time:.6f}",
                "-i", body_video_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", ar_str,
                "-ac", "2",
                "-pix_fmt", "yuv420p",
                "-video_track_timescale", tb_den,
                "-af", "afade=t=out:st=0:d=5.0",
                "-t", "5.0",
                temp_outro_video_path
            ]
            subprocess.run(cmd_outro, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        scale_filter = f"scale={v_width}:{v_height}:force_original_aspect_ratio=decrease,pad={v_width}:{v_height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        if not is_last_clip and os.path.exists(temp_outro_video_path):
            typer.echo(f"Compiling (Intro -> Body -> Outro) into {out_path}...")
            cmd_concat = [
                "ffmpeg", "-y",
                "-i", intro_video_path,
                "-i", body_video_path,
                "-i", temp_outro_video_path,
                "-filter_complex",
                f"[0:v]{scale_filter},settb=1/90000[v0];"
                f"[1:v]{scale_filter},settb=1/90000[v1];"
                f"[2:v]{scale_filter},settb=1/90000[v2];"
                "[v0][v1]concat=n=2:v=1:a=0[v01];"
                "[v01]settb=1/90000[v01tb];"
                f"[v01tb][v2]xfade=transition=fade:duration=1.0:offset={2.0 + body_duration - 1.0:.3f}[v];"
                "[0:a][1:a]concat=n=2:v=0:a=1[a0];"
                "[a0][2:a]acrossfade=d=1.0:c1=tri:c2=tri[a]",
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                out_path
            ]
        else:
            typer.echo(f"Compiling (Intro -> Body) into {out_path}...")
            cmd_concat = [
                "ffmpeg", "-y",
                "-i", intro_video_path,
                "-i", body_video_path,
                "-filter_complex",
                f"[0:v]{scale_filter},settb=1/90000[v0];"
                f"[1:v]{scale_filter},settb=1/90000[v1];"
                "[v0][v1]concat=n=2:v=1:a=0[v];"
                "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                out_path
            ]
        res_concat = subprocess.run(cmd_concat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if res_concat.returncode == 0:
            typer.echo(f"Successfully compiled clip: {out_path}")
            
            # Sync compiled clip to docs/assets/clips/ for preview player UI
            docs_clips_dir = os.path.join("docs", "episodes", episode, "clips") if episode else os.path.join("docs", "assets", "clips")
            os.makedirs(docs_clips_dir, exist_ok=True)
            try:
                shutil.copy2(out_path, os.path.join(docs_clips_dir, out_filename))
                typer.echo(f"Synced compiled clip to {os.path.join(docs_clips_dir, out_filename)}")
            except Exception as e:
                typer.echo(f"Warning: Could not sync to docs: {e}")
            
            # Check final duration warning against the 2m 55s limit (175s)
            try:
                cmd_dur = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", out_path
                ]
                dur_res = subprocess.run(cmd_dur, stdout=subprocess.PIPE, text=True)
                if dur_res.returncode == 0:
                    final_dur = float(dur_res.stdout.strip())
                    if final_dur > 175.0:
                        typer.echo(f"\n⚠️  WARNING: Final compiled clip duration ({final_dur:.2f}s) exceeds the 2m 55s limit (175s)!")
            except Exception:
                pass
        else:
            typer.echo(f"Error concatenating: {res_concat.stderr}", err=True)
            raise typer.Exit(code=1)

    finally:
        # Clean up temp files
        temp_files_to_remove = [
            temp_img_path, intro_video_path, concat_txt_path, temp_body_path, 
            temp_extracted_frame, temp_img_outro_path, temp_outro_video_path
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
        {"index": 2, "name": "Storyboarding", "icon": "🧠", "label": "Structuring Clip Boundaries"},
        {"index": 3, "name": "Audio Cutting", "icon": "✂️", "label": "Normalizing Audio Clips"},
        {"index": 4, "name": "Draft Muxing", "icon": "🎥", "label": "Muxing Black Canvas Videos"},
        {"index": 5, "name": "Rendering Intros", "icon": "🎬", "label": "Compiling Intros & Outros"},
        {"index": 6, "name": "Manifest Sync", "icon": "🚀", "label": "Registering Episode Manifest"}
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
    mode: str = typer.Option("structured", help="Ingestion mode: 'structured' (fast uniform sentence snapping) or 'unstructured' (Gemini AI topic discovery)")
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

    update_ingestion_progress(proj_dir, 1, 5, "Initializing workspace and copying source audio...", f"Started ingestion pipeline for Episode {episode}: {title} (Mode: {mode})")

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
        update_ingestion_progress(proj_dir, 1, 15, f"Transcribing {audio_dest_name} via OpenAI Whisper...", "Running Whisper transcription with word timestamps (tiny.en)...")
        typer.echo(f"Transcribing {audio_dest_path} with Whisper...")
        transcribe(audio=audio_dest_path, model_name="tiny.en", out=trans_path, word_timestamps=True)
        if os.path.exists("transcription.json") and not os.path.exists(trans_path):
            shutil.copy2("transcription.json", trans_path)

    update_ingestion_progress(proj_dir, 2, 30, "Whisper transcription ready. Analyzing structural timestamps...", "Transcription complete with word-level timestamps.")

    # 3. Generate Plan
    plan_path = os.path.join(proj_dir, "plan.json")
    clips_list = []
    if os.path.exists(trans_path):
        update_ingestion_progress(proj_dir, 2, 35, f"Structuring audio into {num_clips} ~2-minute topic clips...", f"Dividing timeline into {num_clips} structural segments.")
        typer.echo(f"Generating structural plan with {num_clips} clips...")
        with open(trans_path, "r", encoding="utf-8") as tf:
            t_data = json.load(tf)
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
            c_obj["title"] = f"{title} Part {c_num}" if c_num > 1 else title
            clips_list.append(c_obj)
            curr_start = end_idx + 1
            if curr_start >= len(words):
                break

        with open(plan_path, "w", encoding="utf-8") as pf:
            json.dump(clips_list, pf, indent=2)

    update_ingestion_progress(proj_dir, 3, 40, f"Generated plan.json with {len(clips_list)} clips. Starting audio cuts...", f"Created storyboard plan with {len(clips_list)} clips.")

    # 4. Sync plan.json to snapshot, root, and docs
    snapshot_path = os.path.join(proj_dir, "plan_snapshot.json")
    shutil.copy2(plan_path, snapshot_path)
    shutil.copy2(plan_path, "plan.json")
    docs_ep_dir = os.path.join("docs", "episodes", str(episode))
    os.makedirs(docs_ep_dir, exist_ok=True)
    shutil.copy2(plan_path, os.path.join(docs_ep_dir, "plan.json"))

    # 5. Audio Cut
    update_ingestion_progress(proj_dir, 3, 45, "Slicing audio clips with EBU R128 loudness normalization...", "Re-encoding audio slices to -16 LUFS / -1.5 dB Peak...")
    typer.echo(f"Cutting sample-accurate audio clips with EBU R128 normalization...")
    cut(audio=audio_dest_path, plan_file=plan_path, out_dir="clips")

    update_ingestion_progress(proj_dir, 4, 55, "Audio slicing complete. Starting black canvas draft video muxing...", "All audio clips normalized and saved.")

    # 6. Mux & Compile Clips
    total_clips = max(1, len(clips_list))
    for idx, c in enumerate(clips_list):
        n = c["num"]
        mux_pct = 55 + int((idx / total_clips) * 15)
        update_ingestion_progress(proj_dir, 4, mux_pct, f"Draft-muxing Clip {n} of {total_clips}...", f"Generating 740x740 black video canvas for Clip {n}")
        mux_clip(num=n, plan_file=plan_path, audio_dir="clips", out_dir="clips")

        comp_pct = 70 + int((idx / total_clips) * 25)
        update_ingestion_progress(proj_dir, 5, comp_pct, f"Compiling Title Intro & Outro for Clip {n} of {total_clips}...", f"Rendering 2s Title Card Intro & 5s Curiosity Question Outro for Clip {n}")
        compile_clip(num=n, plan_file=plan_path, master_dir="clips", out_dir="clips", backup=True)

    # 7. Register in docs/episodes.json
    update_ingestion_progress(proj_dir, 6, 95, "Syncing episode manifest and preview player assets...", "Updating docs/episodes.json for GitHub Pages routing.")
    ep_manifest_path = os.path.join("docs", "episodes.json")
    if os.path.exists(ep_manifest_path):
        try:
            with open(ep_manifest_path, "r", encoding="utf-8") as mf:
                manifest = json.load(mf)
            
            # Deduplicate manifest by episode id/number
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

    update_ingestion_progress(proj_dir, 6, 100, "Episode ingestion complete! Project ready in Curator.", f"Episode {episode} ingestion pipeline completed successfully.")
    typer.echo(f"[SUCCESS] Episode {episode} ingestion pipeline complete! Project ready in Curator & Preview Player.")


if __name__ == "__main__":
    app()
