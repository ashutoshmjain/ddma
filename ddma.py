import typer
import whisper
import json
import os
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

def adjust_clip_start(start: float, end: float, segments: list) -> float:
    # Gather all words across all segments
    all_words = []
    for seg in segments:
        for w in seg.get("words", []):
            all_words.append(w)
    
    # Filter words starting after or very close to start
    words_after = [w for w in all_words if w["start"] >= start]
    if not words_after:
        return start
        
    filler_words = {"so", "yeah", "um", "uh", "well", "like", "but", "and", "now", "right"}
    
    curr_idx = 0
    skipped_count = 0
    while curr_idx < len(words_after) and skipped_count < 3:
        w = words_after[curr_idx]
        w_text = w["word"].strip().lower().translate(str.maketrans("", "", '.,?!-;"\''))
        if w_text in filler_words:
            if curr_idx + 1 < len(words_after):
                next_w = words_after[curr_idx + 1]
                if next_w["start"] - start < 2.0:
                    curr_idx += 1
                    skipped_count += 1
                    continue
        break
        
    if curr_idx < len(words_after):
        adjusted = words_after[curr_idx]["start"]
        return max(start, adjusted - 0.05)
    return start

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

            # Adjust the start of the clip to strip leading filler/silence
            adjusted_start = adjust_clip_start(start_aligned, end_aligned, segments)
            duration = end_aligned - adjusted_start
            if duration > max_duration:
                typer.echo(f"Warning: Aligned clip {idx + 1} duration ({duration:.2f}s) exceeds max_duration ({max_duration}s).")
            
            clips_plan.append({
                "num": idx + 1,
                "title": "",
                "start": adjusted_start,
                "end": end_aligned,
                "duration": duration
            })
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

        t_curr = 0.0
        clip_num = 1

        while t_curr < total_duration:
            candidates = [b for b in boundary_candidates if b["time"] > t_curr]
            if not candidates:
                break
            
            # Find boundaries falling in the min/max window
            valid_candidates = [b for b in candidates if min_duration <= (b["time"] - t_curr) <= max_duration]
            
            if valid_candidates:
                # Score candidates to preserve clip integrity:
                # 1. Punctuation at end (weight +2.0)
                # 2. Size of silent gap following the segment (weight up to +1.5)
                # 3. Preference for longer clips within limits (weight up to +0.5)
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

            adjusted_start = adjust_clip_start(t_curr, target_b, segments)
            clip_duration = target_b - adjusted_start

            clips_plan.append({
                "num": clip_num,
                "title": "",
                "start": adjusted_start,
                "end": target_b,
                "duration": clip_duration
            })

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
            out_filename = f"{base_name}-{c['num']}-{title}.mp3"
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
    search_pattern1 = os.path.join(audio_dir, f"*-{num}.mp3")
    search_pattern2 = os.path.join(audio_dir, f"*-{num}-*.mp3")
    audio_files = glob.glob(search_pattern1) + glob.glob(search_pattern2)

    if not audio_files:
        typer.echo(f"Error: No audio file found in {audio_dir} for clip {num}.", err=True)
        raise typer.Exit(code=1)
    
    audio_path = audio_files[0]
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    episode = base_name.split("-")[0]

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
    episode_title: str = typer.Option("Life, Death and the Lysosome", help="Title of the episode")
):
    """
    Mux and compile a clip with dynamic title card intro and finished Mosaic video.
    """
    import shutil
    import glob

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

    # 1. Locate the master clip (e.g. clips/242-4.mp4)
    search_pattern = os.path.join(master_dir, f"*-{num}.mp4")
    master_files = [f for f in glob.glob(search_pattern) if not f.endswith("-original.mp4")]

    if not master_files:
        typer.echo(f"Error: No finished video found in {master_dir} for clip {num}.", err=True)
        raise typer.Exit(code=1)

    master_path = master_files[0]
    base_name = os.path.splitext(os.path.basename(master_path))[0]
    episode = base_name.split("-")[0]

    backup_path = os.path.join(master_dir, f"{base_name}-original.mp4")

    # 2. Back up original master clip if needed
    if backup:
        if not os.path.exists(backup_path):
            typer.echo(f"Creating backup of original clip to {backup_path}...")
            shutil.copy2(master_path, backup_path)
        else:
            typer.echo(f"Backup already exists at {backup_path}")
    else:
        backup_path = master_path

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
        # Extract frame at 1.0s of backup master video as title card background
        extracted = False
        if os.path.exists(backup_path):
            cmd_extract = [
                "ffmpeg", "-y",
                "-ss", "00:00:01.000",
                "-i", backup_path,
                "-vframes", "1",
                temp_extracted_frame
            ]
            try:
                res_extract = subprocess.run(cmd_extract, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res_extract.returncode == 0 and os.path.exists(temp_extracted_frame):
                    extracted = True
            except Exception as e:
                typer.echo(f"Warning: Could not extract frame from master clip: {e}")

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

        # Open image canvas
        from PIL import Image, ImageDraw, ImageFont
        if extracted:
            image = Image.open(temp_extracted_frame).convert("RGBA")
            width, height = image.size
        else:
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

        if num == 1:
            sub_text = f"EPISODE {episode}"
            title_text = ep_title
        else:
            sub_text = f"EPISODE {episode} • PART {num}"
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

        # 6. Equalize master body durations if mismatch > 0.05 seconds to prevent drift/desync
        body_video_path = backup_path
        temp_body_path = f"temp_body_{num}.mp4"
        if v_dur is not None and a_dur is not None and abs(v_dur - a_dur) > 0.05:
            min_dur = min(v_dur, a_dur)
            typer.echo(f"Equalizing master stream durations (video={v_dur:.3f}s, audio={a_dur:.3f}s)...")
            typer.echo(f"Trimming master body to {min_dur:.3f}s...")
            cmd_norm = [
                "ffmpeg", "-y",
                "-i", backup_path,
                "-ss", "0",
                "-t", f"{min_dur:.3f}",
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
                typer.echo("Master body successfully equalized.")
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
        subprocess.run(cmd_intro, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
                bridge_text = "Next question is coming up..."

            # Generate outro image
            img_outro = Image.new("RGB", (width, height), color=(0, 0, 0))
            draw_outro = ImageDraw.Draw(img_outro)
            
            if font_path_bold and os.path.exists(font_path_bold):
                font_outro = ImageFont.truetype(font_path_bold, 34)
            else:
                font_outro = ImageFont.load_default()

            def wrap_text_outro(text, font_obj, max_w):
                words = text.split()
                lines = []
                curr = []
                for word in words:
                    test_line = " ".join(curr + [word])
                    bbox = draw_outro.textbbox((0, 0), test_line, font=font_obj)
                    w = bbox[2] - bbox[0]
                    if w <= max_w:
                        curr.append(word)
                    else:
                        if curr:
                            lines.append(" ".join(curr))
                        curr = [word]
                if curr:
                    lines.append(" ".join(curr))
                return lines

            lines_outro = wrap_text_outro(bridge_text, font_outro, width - 160)
            line_spacing_outro = 18
            line_heights_outro = []
            total_h_outro = 0
            for line in lines_outro:
                bbox = draw_outro.textbbox((0, 0), line, font=font_outro)
                h = bbox[3] - bbox[1]
                line_heights_outro.append(h)
                total_h_outro += h
            total_h_outro += line_spacing_outro * (len(lines_outro) - 1)

            curr_y_outro = (height - total_h_outro) // 2
            for idx, line in enumerate(lines_outro):
                bbox = draw_outro.textbbox((0, 0), line, font=font_outro)
                w = bbox[2] - bbox[0]
                draw_outro.text(((width - w) // 2, curr_y_outro), line, font=font_outro, fill=(255, 255, 255))
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

        if not is_last_clip and os.path.exists(temp_outro_video_path):
            typer.echo(f"Compiling with cross-fade (Intro -> Body -> Outro) into {out_path}...")
            cmd_concat = [
                "ffmpeg", "-y",
                "-i", intro_video_path,
                "-i", body_video_path,
                "-i", temp_outro_video_path,
                "-filter_complex",
                "[0:v]settb=1/90000[v0];"
                "[1:v]settb=1/90000[v1];"
                "[2:v]settb=1/90000[v2];"
                "[v0][v1]xfade=transition=fade:duration=1.0:offset=1.0[v01];"
                f"[v01][v2]xfade=transition=fade:duration=1.0:offset={body_duration + 1.0 - 1.0:.3f}[v];"
                "[0:a][1:a]acrossfade=d=1.0:c1=tri:c2=tri[a0];"
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
            typer.echo(f"Compiling with cross-fade (Intro -> Body) into {out_path}...")
            cmd_concat = [
                "ffmpeg", "-y",
                "-i", intro_video_path,
                "-i", body_video_path,
                "-filter_complex",
                "[0:v]settb=1/90000[v0];"
                "[1:v]settb=1/90000[v1];"
                "[v0][v1]xfade=transition=fade:duration=1.0:offset=1.0[v];"
                "[0:a][1:a]acrossfade=d=1.0:c1=tri:c2=tri[a]",
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
            docs_clips_dir = os.path.join("docs", "assets", "clips")
            os.makedirs(docs_clips_dir, exist_ok=True)
            try:
                shutil.copy2(out_path, os.path.join(docs_clips_dir, out_filename))
                typer.echo(f"Synced compiled clip to {os.path.join(docs_clips_dir, out_filename)}")
            except Exception as e:
                typer.echo(f"Warning: Could not sync to docs/assets/clips: {e}")
            
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


if __name__ == "__main__":
    app()
