import os
import re
import subprocess
import sys
import json
from PIL import Image, ImageDraw, ImageFont

def wrap_text(text, font, max_width):
    lines = []
    # Support explicit newlines in the JSON string
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            img_temp = Image.new("RGB", (10, 10))
            draw_temp = ImageDraw.Draw(img_temp)
            bbox = draw_temp.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
        if current_line:
            lines.append(" ".join(current_line))
    return lines

def render_bridge_image(bridge_text_input, width, height, font_path, out_img_path):
    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Use bold font for readability
    if os.path.exists(font_path):
        font = ImageFont.truetype(font_path, 34)
    else:
        font = ImageFont.load_default()
        
    # Convert input to a single string question
    if isinstance(bridge_text_input, list):
        text = " ".join(bridge_text_input)
    else:
        text = str(bridge_text_input).strip()
        
    # Wrap text to fit inside width with 80px margin on each side (max_width = width - 160)
    lines = wrap_text(text, font, width - 160)
    
    # Calculate total height of the text block to center it vertically
    line_spacing = 18
    line_heights = []
    total_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        line_heights.append(h)
        total_height += h
    total_height += line_spacing * (len(lines) - 1)
    
    # Draw centered text lines (fully centered horizontally)
    current_y = (height - total_height) // 2
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (width - w) // 2
        draw.text((x, current_y), line, font=font, fill=(255, 255, 255))
        current_y += line_heights[idx] + line_spacing
        
    img.save(out_img_path)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Combine episode clips with transition bridge cards.")
    parser.add_argument("--episode", type=str, required=True, help="Episode number/prefix (e.g. 244)")
    parser.add_argument("--plan-file", type=str, default="plan.json", help="Path to plan JSON file")
    parser.add_argument("--out-file", type=str, help="Output path for the combined video file")
    args = parser.parse_args()

    clips_dir = "clips"
    episode = args.episode
    plan_file = args.plan_file
    
    if not os.path.exists(plan_file):
        print(f"Error: Plan file {plan_file} not found.")
        sys.exit(1)
        
    with open(plan_file, "r", encoding="utf-8") as f:
        plan_data = json.load(f)
    
    pattern = re.compile(rf"^{episode}-(\d+)\.mp4$")
    
    locked_nums = {c["num"] for c in plan_data if c.get("locked", False) and not c.get("hidden", False)}
    
    clip_files = []
    if os.path.exists(clips_dir):
        for f in os.listdir(clips_dir):
            match = pattern.match(f)
            if match:
                num = int(match.group(1))
                if num in locked_nums:
                    clip_files.append((num, os.path.abspath(os.path.join(clips_dir, f))))
                
    if not clip_files:
        print(f"Error: No locked, compiled video clips found for Episode {episode} in '{clips_dir}' directory.")
        sys.exit(1)
        
    # Sort clips numerically
    clip_files.sort(key=lambda x: x[0])
    
    print("Found and sorted clips for combination:")
    for num, path in clip_files:
        print(f"  Clip {num}: {os.path.basename(path)}")
        
    # Probe Clip 1 to match video/audio properties exactly
    v_width = 740
    v_height = 740
    fps_str = "30"
    ar_str = "48000"
    tb_den = "90000"
    
    try:
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", clip_files[0][1]
        ]
        probe_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True)
        if probe_res.returncode == 0:
            data = json.loads(probe_res.stdout)
            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type")
                if codec_type == "video":
                    v_width = stream.get("width", 740)
                    v_height = stream.get("height", 740)
                    avg_fps = stream.get("avg_frame_rate")
                    r_fps = stream.get("r_frame_rate")
                    fps_str = avg_fps if avg_fps and avg_fps != "0/0" else r_fps
                    if not fps_str or "/" not in fps_str:
                        fps_str = "30"
                    tb_str = stream.get("time_base")
                    if tb_str and "/" in tb_str:
                        tb_den = tb_str.split("/")[1]
                elif codec_type == "audio":
                    ar_str = stream.get("sample_rate", "48000")
    except Exception as e:
        print(f"Warning probing clip properties: {e}. Using defaults.")

    # Build a frame-accurate FFmpeg filtergraph
    # Normalizes all clips to exact 740x740, 30 fps, setsar=1, and 48kHz stereo AAC
    # Clip 1 retains full start (t=0.0s). Clips 2+ are trimmed at exactly t=2.0s with frame-accurate PTS.
    out_path = args.out_file if args.out_file else f"combined_{episode}.mp4"
    print(f"Concatenating {len(clip_files)} clips into {out_path} with frame-accurate 30 fps and 48 kHz stereo AAC audio...")
    
    cmd = ["ffmpeg", "-y"]
    filter_parts = []
    concat_inputs = []
    
    # Map clip numbers to plan_data entries
    clip_map = {c.get("num"): c for c in plan_data}

    for i, (num, path) in enumerate(clip_files):
        cmd.extend(["-i", path])
        clip_entry = clip_map.get(num, {})
        default_trim = 0.0 if (i == 0 or num == 1) else 2.0
        intro_trim = float(clip_entry.get("intro_trim", default_trim))
        
        if intro_trim <= 0.0:
            # Keep full video from start (t=0.0s)
            v_filter = f"[{i}:v]scale={v_width}:{v_height}:force_original_aspect_ratio=decrease,pad={v_width}:{v_height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,setpts=PTS-STARTPTS[v{i}]"
            a_filter = f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]"
        else:
            v_filter = f"[{i}:v]trim=start={intro_trim:.3f},setpts=PTS-STARTPTS,scale={v_width}:{v_height}:force_original_aspect_ratio=decrease,pad={v_width}:{v_height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]"
            a_filter = f"[{i}:a]atrim=start={intro_trim:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo[a{i}]"
        
        filter_parts.append(v_filter)
        filter_parts.append(a_filter)
        concat_inputs.append(f"[v{i}][a{i}]")
        
    concat_filter = f"{''.join(concat_inputs)}concat=n={len(clip_files)}:v=1:a=1[v_out][a_out]"
    filter_complex = ";".join(filter_parts) + ";" + concat_filter
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", "[a_out]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-video_track_timescale", "90000",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        out_path
    ])
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"\nSuccessfully generated combined video: {out_path}")
        
        # Verify audio/video stream duration equalization
        try:
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_streams", "-of", "json", out_path
            ]
            probe_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True)
            if probe_res.returncode == 0:
                data = json.loads(probe_res.stdout)
                v_dur = None
                a_dur = None
                for stream in data.get("streams", []):
                    codec_type = stream.get("codec_type")
                    dur = stream.get("duration")
                    if dur is not None:
                        if codec_type == "video":
                            v_dur = float(dur)
                        elif codec_type == "audio":
                            a_dur = float(dur)
                print(f"Combined Video Stream Duration: {v_dur}s")
                print(f"Combined Audio Stream Duration: {a_dur}s")
                if v_dur is not None and a_dur is not None:
                    diff = abs(v_dur - a_dur)
                    print(f"A/V Duration Difference: {diff:.6f}s")
        except Exception as e:
            print(f"Could not probe final A/V streams: {e}")
    else:
        print(f"\nError combining clips: {res.stderr}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
