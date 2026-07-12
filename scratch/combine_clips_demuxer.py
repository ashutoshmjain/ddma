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
    
    # Filter to only pick up locked clip numbers from the plan
    locked_nums = {c["num"] for c in plan_data if c.get("locked", False)}
    
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

    # Generate transition bridge videos for each gap
    font_path = "C:\\Windows\\Fonts\\segoeuib.ttf" # Segoe UI Bold
    for i, (num, path) in enumerate(clip_files[:-1]):
        clip_data = None
        for c in plan_data:
            if c["num"] == num:
                clip_data = c
                break
                
        bridge_text = clip_data.get("bridge_text", "") if clip_data else ""
        gap_path = f"temp_gap_{num}.mp4"
        
        # Probe preceding clip duration to locate the end audio
        clip_dur = None
        try:
            dur_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path
            ]
            dur_res = subprocess.run(dur_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if dur_res.returncode == 0:
                clip_dur = float(dur_res.stdout.strip())
        except Exception as e:
            print(f"Warning: Could not probe clip duration for {path}: {e}")

        if bridge_text:
            print(f"Generating 5.0s bridge card for Clip {num} -> Clip {num+1}...")
            temp_img = f"temp_bridge_{num}.png"
            render_bridge_image(bridge_text, v_width, v_height, font_path, temp_img)
            
            # Map the preceding clip's final 5.0s of audio and apply fade-out
            if clip_dur is not None and clip_dur >= 5.0:
                start_time = clip_dur - 5.0
                print(f"  Extracting preceding audio starting at {start_time:.2f}s and fading out...")
                cmd_gap = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-r", fps_str,
                    "-i", temp_img,
                    "-ss", f"{start_time:.6f}",
                    "-i", path,
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-video_track_timescale", tb_den,
                    "-af", "afade=t=out:st=0:d=5.0",
                    "-c:a", "aac",
                    "-ar", ar_str,
                    "-ac", "2",
                    "-t", "5.0",
                    gap_path
                ]
            else:
                # Fallback to silent gap if preceding clip is too short or dur lookup failed
                cmd_gap = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-r", fps_str,
                    "-i", temp_img,
                    "-f", "lavfi", "-i", f"anullsrc=cl=stereo:r={ar_str}",
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-video_track_timescale", tb_den,
                    "-c:a", "aac",
                    "-ar", ar_str,
                    "-ac", "2",
                    "-t", "5.0",
                    gap_path
                ]
                
            res_gap = subprocess.run(cmd_gap, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if os.path.exists(temp_img):
                os.remove(temp_img)
                
            if res_gap.returncode != 0:
                print(f"Error generating bridge video: {res_gap.stderr}", file=sys.stderr)
                sys.exit(1)
        else:
            # Fallback to a simple 1.0s gap if no bridge text is provided
            print(f"Generating 1.0s gap for Clip {num} -> Clip {num+1} (no bridge text)...")
            if clip_dur is not None and clip_dur >= 1.0:
                start_time = clip_dur - 1.0
                cmd_gap = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", f"color=c=black:s={v_width}x{v_height}:r={fps_str}",
                    "-ss", f"{start_time:.6f}",
                    "-i", path,
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-video_track_timescale", tb_den,
                    "-af", "afade=t=out:st=0:d=1.0",
                    "-c:a", "aac",
                    "-ar", ar_str,
                    "-ac", "2",
                    "-t", "1.0",
                    gap_path
                ]
            else:
                cmd_gap = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", f"color=c=black:s={v_width}x{v_height}:r={fps_str}",
                    "-f", "lavfi", "-i", f"anullsrc=cl=stereo:r={ar_str}",
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-video_track_timescale", tb_den,
                    "-c:a", "aac",
                    "-ar", ar_str,
                    "-ac", "2",
                    "-t", "1.0",
                    gap_path
                ]
                
            res_gap = subprocess.run(cmd_gap, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_gap.returncode != 0:
                print(f"Error generating default gap: {res_gap.stderr}", file=sys.stderr)
                sys.exit(1)

    # Write demuxer list file
    list_path = "concat_list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for i, (num, path) in enumerate(clip_files):
            # FFmpeg concat demuxer paths need forward slashes and escaped single quotes
            safe_path = path.replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
            
            # Insert the transition video only between clips (not after the last one)
            if i < len(clip_files) - 1:
                gap_path = f"temp_gap_{num}.mp4"
                safe_gap_path = os.path.abspath(gap_path).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{safe_gap_path}'\n")
            
    print(f"\nCreated demuxer list: {list_path}")
    
    out_path = args.out_file if args.out_file else f"combined_{episode}.mp4"
    print(f"Concatenating into {out_path} at constant 30 fps and 48 kHz stereo AAC audio...")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c:v", "libx264",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        out_path
    ]
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Clean up demuxer list file and temp gap files
    if os.path.exists(list_path):
        os.remove(list_path)
    for num, _ in clip_files[:-1]:
        gap_path = f"temp_gap_{num}.mp4"
        if os.path.exists(gap_path):
            try:
                os.remove(gap_path)
            except Exception:
                pass
        
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
