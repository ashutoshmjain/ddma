import os
import sys
import re
import json
import time
import math
import subprocess
import av
from multiprocessing import Pool, cpu_count
from PIL import Image, ImageDraw, ImageFont

# Set up paths relative to github root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GITHUB_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from longform_video_engine import map_timeline_with_stings_and_cuts

EP_NUM = "248"
AUDIO_PATH = os.path.join(GITHUB_ROOT, "deepDive", "src", "ddma", "docs", "episodes", EP_NUM, f"podcast_{EP_NUM}.mp3")
TRANS_PATH = os.path.join(GITHUB_ROOT, "deepDive", "src", "ddma", "docs", "episodes", EP_NUM, "transcription.json")
EDIT_PATH = os.path.join(GITHUB_ROOT, "deepDive", "src", "ddma", "docs", "episodes", EP_NUM, "podcast_edit.json")
PLAN_PATH = os.path.join(GITHUB_ROOT, "ddma", "projects", f"episode_{EP_NUM}", "plan.json")
ARCHETYPES_DIR = os.path.join(GITHUB_ROOT, "ddma", "archetypes")
MEDIA_VIDEOS_DIR = os.path.join(GITHUB_ROOT, "media", "videos")

CLIPS_DIR = os.path.join(GITHUB_ROOT, "ddma", "clips")
TEMP_CHUNKS_DIR = os.path.join(CLIPS_DIR, "temp_chunks")
FINAL_MASTER_MP4 = os.path.join(CLIPS_DIR, f"{EP_NUM}-longform-master.mp4")

def get_bezier_curve(p0, p1, p2, p3, steps=10):
    points = []
    for i in range(steps + 1):
        u = i / steps
        uu = 1 - u
        x = uu**3 * p0[0] + 3 * uu**2 * u * p1[0] + 3 * uu * u**2 * p2[0] + u**3 * p3[0]
        y = uu**3 * p0[1] + 3 * uu**2 * u * p1[1] + 3 * uu * u**2 * p2[1] + u**3 * p3[1]
        points.append((x, y))
    return points

def draw_vector_clip_mic(draw, cx, cy, scale=0.65, fill=(255, 255, 255)):
    capsule_pts = []
    capsule_pts.append((-10, -24))
    capsule_pts.extend(get_bezier_curve((-10, -24), (-10, -32), (10, -32), (10, -24))[1:])
    capsule_pts.append((10, 0))
    capsule_pts.extend(get_bezier_curve((10, 0), (10, 7), (-10, 7), (-10, 0))[1:])
    capsule_pts.append((-10, -24))

    cradle_pts = []
    cradle_pts.append((-14, -5))
    cradle_pts.extend(get_bezier_curve((-14, -5), (-14, 13), (14, 13), (14, -5))[1:])
    cradle_pts.append((16, -5))
    cradle_pts.extend(get_bezier_curve((16, -5), (16, 17), (-16, 17), (-16, -5))[1:])
    cradle_pts.append((-14, -5))

    stand_pts = [
        (-2, 15), (2, 15), (2, 23), (11, 23), (11, 26),
        (-11, 26), (-11, 23), (-2, 23)
    ]

    y_shift = 3
    for pts in [capsule_pts, cradle_pts, stand_pts]:
        scaled_pts = [(cx + x * scale, cy + (y + y_shift) * scale) for x, y in pts]
        draw.polygon(scaled_pts, fill=fill)

def find_system_fonts():
    candidates = [
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            return reg, bold
    return None, None

def build_manim_scene_timeline(plan_data, total_duration):
    """
    Maps all 389 compiled Manim MP4 scenes across the 23 clips onto a continuous
    non-overlapping timeline from 0.0s to total_duration.
    """
    raw_intervals = []

    # Optional: If Scene01_RobotWildernessFallacy exists for the pre-sting intro (0.0s - 29.68s), include it
    intro_mp4 = os.path.join(MEDIA_VIDEOS_DIR, "chapter_01_scenes_strict", "740p30", "Scene01_RobotWildernessFallacy.mp4")

    for clip_num in range(1, len(plan_data) + 1):
        clip = plan_data[clip_num - 1]
        c_start = float(clip.get("start", 0.0))
        c_end = float(clip.get("end", c_start + 120.0))

        py_path = os.path.join(ARCHETYPES_DIR, f"clip_{clip_num:02d}_gemini_scenes.py")
        v_dir = os.path.join(MEDIA_VIDEOS_DIR, f"clip_{clip_num:02d}_gemini_scenes", "740p15")

        if not os.path.exists(py_path) or not os.path.exists(v_dir):
            continue

        with open(py_path, "r", encoding="utf-8") as fp:
            classes = re.findall(r"class\s+(Scene\w+)\s*\(", fp.read())

        mp4s = [
            os.path.join(v_dir, f"{sc}.mp4")
            for sc in classes
            if os.path.exists(os.path.join(v_dir, f"{sc}.mp4"))
        ]
        if not mp4s:
            continue

        # For Clip 1, pre-sting (0 -> 29.68s) uses intro_mp4 if available, and post-sting (39.68s -> c_end) uses Clip 1 scenes
        if clip_num == 1 and os.path.exists(intro_mp4):
            raw_intervals.append({
                "start": 0.0,
                "end": 29.68,
                "mp4": intro_mp4,
                "fps": 30
            })
            eff_start = 39.68
        else:
            eff_start = c_start

        n = len(mp4s)
        beat_dur = max(1.0, (c_end - eff_start) / n)
        for idx, mp4_path in enumerate(mp4s):
            b_st = eff_start + idx * beat_dur
            b_en = c_end if idx == n - 1 else eff_start + (idx + 1) * beat_dur
            raw_intervals.append({
                "start": b_st,
                "end": b_en,
                "mp4": mp4_path,
                "fps": 15
            })

    raw_intervals.sort(key=lambda x: x["start"])

    # Close any small inter-clip gaps so every frame has an active Manim scene
    for i in range(len(raw_intervals) - 1):
        # Do not overwrite the welcome sting window (29.68s -> 39.68s)
        if abs(raw_intervals[i]["end"] - 29.68) < 0.5:
            continue
        if raw_intervals[i]["end"] < raw_intervals[i + 1]["start"]:
            raw_intervals[i]["end"] = raw_intervals[i + 1]["start"]

    if raw_intervals and raw_intervals[-1]["end"] < total_duration:
        raw_intervals[-1]["end"] = total_duration + 1.0

    return raw_intervals

def render_chunk_worker(args):
    chunk_idx, start_t, end_t, out_path, trans_segments, scene_intervals, fps = args
    t_start_chunk = time.time()
    num_frames = int(round((end_t - start_t) * fps))
    print(f"[{chunk_idx+1}] Starting chunk {start_t:.1f}s -> {end_t:.1f}s ({num_frames} frames)...", flush=True)

    f_reg, f_bold = find_system_fonts()
    font_host = ImageFont.truetype(f_bold or "arial.ttf", 20)
    font_caption = ImageFont.truetype(f_bold or "arial.ttf", 36)
    font_fine = ImageFont.truetype(f_reg or "arial.ttf", 15)
    font_badge = ImageFont.truetype(f_bold or "arial.ttf", 22)
    font_title_lg = ImageFont.truetype(f_bold or "arial.ttf", 60)
    font_sub_md = ImageFont.truetype(f_reg or "arial.ttf", 24)

    cmd_ffmpeg = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1920x1080",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        out_path
    ]

    proc = subprocess.Popen(cmd_ffmpeg, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # Single-scene LRU cache in worker so only 1 Manim MP4 is decoded in RAM at a time
    cached_mp4_path = None
    cached_frames = []

    box_x = 590
    box_y = 260

    for i in range(num_frames):
        t = start_t + (i / fps)

        frame_img = Image.new("RGB", (1920, 1080), (0, 0, 0))
        draw = ImageDraw.Draw(frame_img)

        # 1. Centerpiece Display (drawn first so upper-canvas host strip & subtitles overlay cleanly)
        if 29.68 <= t <= 39.68:
            # Welcome Sting: Borderless Podcast Title Artwork Card
            cy = 560
            draw.text((960, cy - 170), "D E E P   D I V E   P O D C A S T", font=font_badge, fill=(180, 190, 205), anchor="mm")
            draw.text((960, cy - 110), f"E P I S O D E   {EP_NUM}", font=font_fine, fill=(140, 150, 165), anchor="mm")
            draw.text((960, cy - 35), "WHAT EXACTLY IS AI AUTONOMY?", font=font_title_lg, fill=(255, 255, 255), anchor="mm")
            draw.text((960, cy + 55), "The Architecture of Sovereign Intelligence • Research to Reality", font=font_sub_md, fill=(200, 210, 225), anchor="mm")
            draw.text((960, cy + 145), "HOSTED BY SATOSHA & SATOSHI", font=font_badge, fill=(160, 170, 185), anchor="mm")
            draw.text((960, cy + 200), f"deepdive.shutri.com/{EP_NUM}.html", font=font_fine, fill=(110, 120, 135), anchor="mm")
        else:
            # Pre-sting scene01 uses full 740x740 height (box_y=220); post-sting scenes keep top half blank for captions so shift up to box_y=110
            cur_box_y = 220 if t < 29.68 else 110
            cur_sc = next((s for s in scene_intervals if s["start"] <= t < s["end"]), None)
            if not cur_sc and scene_intervals:
                cur_sc = scene_intervals[-1] if t >= scene_intervals[-1]["end"] else scene_intervals[0]

            if cur_sc:
                mp4_path = cur_sc["mp4"]
                if mp4_path != cached_mp4_path:
                    cached_frames = []
                    if os.path.exists(mp4_path):
                        try:
                            container = av.open(mp4_path)
                            for f_av in container.decode(video=0):
                                img = f_av.to_image().convert("RGB")
                                # Mask out the bold Archetype Title at y = -2.95 (pixel rows 622..672)
                                # while keeping the thin footer line (y=679..680) and tiny metadata labels (y=691..701)
                                ImageDraw.Draw(img).rectangle([(0, 622), (740, 672)], fill=(0, 0, 0))
                                cached_frames.append(img)
                            container.close()
                        except Exception:
                            cached_frames = []
                    cached_mp4_path = mp4_path

                if cached_frames:
                    sc_offset = max(0.0, t - cur_sc["start"])
                    sc_fps = cur_sc.get("fps", 15)
                    f_idx = min(len(cached_frames) - 1, int(sc_offset * sc_fps))
                    frame_img.paste(cached_frames[f_idx], (box_x, cur_box_y))

        # 2. Top Host Strip: SATOSHA — 🎙️ — SATOSHI (y=60)
        y_host = 60
        draw.text((860, y_host), "SATOSHA", font=font_host, fill=(226, 232, 240), anchor="ra")
        draw.text((1060, y_host), "SATOSHI", font=font_host, fill=(226, 232, 240), anchor="la")
        draw.line([(875, y_host), (935, y_host)], fill=(71, 85, 105), width=2)
        draw.line([(985, y_host), (1045, y_host)], fill=(71, 85, 105), width=2)

        is_mic_on = (t % 0.8) < 0.48
        mic_color = (255, 255, 255) if is_mic_on else (51, 65, 85)
        draw_vector_clip_mic(draw, 960, y_host, scale=0.65, fill=mic_color)

        # 3. Subtitles Karaoke (y=115..175)
        active_seg = next((s for s in trans_segments if s.get("start", 0) <= t <= s.get("end", 0) + 0.15), None)
        if active_seg and active_seg.get("words"):
            cur_words = active_seg["words"]
            w_lens = [font_caption.getbbox(w.get("word", "").strip() + " ")[2] - font_caption.getbbox(w.get("word", "").strip() + " ")[0] for w in cur_words]
            total_w = sum(w_lens)

            if total_w <= 1700:
                cx = (1920 - total_w) // 2
                cy = 115
                for w, wl in zip(cur_words, w_lens):
                    wt = w.get("word", "").strip() + " "
                    ws = float(w.get("start", 0))
                    we = float(w.get("end", ws + 0.3))
                    col = (255, 214, 10) if ws <= t <= we else (255, 255, 255) if t > we else (115, 115, 115)
                    draw.text((cx, cy), wt, font=font_caption, fill=col)
                    cx += wl
            else:
                half = len(cur_words) // 2
                w1 = sum(w_lens[:half])
                cx1 = (1920 - w1) // 2
                for w, wl in zip(cur_words[:half], w_lens[:half]):
                    wt = w.get("word", "").strip() + " "
                    ws = float(w.get("start", 0))
                    we = float(w.get("end", ws + 0.3))
                    col = (255, 214, 10) if ws <= t <= we else (255, 255, 255) if t > we else (115, 115, 115)
                    draw.text((cx1, 105), wt, font=font_caption, fill=col)
                    cx1 += wl
                w2 = sum(w_lens[half:])
                cx2 = (1920 - w2) // 2
                for w, wl in zip(cur_words[half:], w_lens[half:]):
                    wt = w.get("word", "").strip() + " "
                    ws = float(w.get("start", 0))
                    we = float(w.get("end", ws + 0.3))
                    col = (255, 214, 10) if ws <= t <= we else (255, 255, 255) if t > we else (115, 115, 115)
                    draw.text((cx2, 150), wt, font=font_caption, fill=col)
                    cx2 += wl

        proc.stdin.write(frame_img.tobytes())

    proc.stdin.close()
    proc.wait()
    dur_render = time.time() - t_start_chunk
    print(f"[{chunk_idx+1}] Finished in {dur_render:.1f}s ({num_frames/max(0.1, dur_render):.1f} fps)", flush=True)
    return out_path

def main():
    print(f"==================================================")
    print(f"  Longform Video Master Parallel Render & Concat  ")
    print(f"  Episode {EP_NUM} • 389 Manim Bespoke Scenes     ")
    print(f"==================================================")

    # 1. Load audio duration
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", AUDIO_PATH],
        capture_output=True, text=True
    )
    total_duration = float(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else 3254.21
    print(f"Master Audio Duration: {total_duration:.2f}s ({total_duration/60:.2f} mins)")

    # 2. Load data
    with open(TRANS_PATH, "r", encoding="utf-8") as f:
        trans_data = json.load(f)
    with open(EDIT_PATH, "r", encoding="utf-8") as f:
        edit_data = json.load(f)
    with open(PLAN_PATH, "r", encoding="utf-8") as f:
        plan_data = json.load(f)

    # 3. Build 389-scene Manim timeline
    scene_intervals = build_manim_scene_timeline(plan_data, total_duration)
    print(f"Mapped {len(scene_intervals)} rendered Manim MP4 scenes across {total_duration:.1f}s timeline")

    # 4. Map transcription with cuts & stings
    fps = 25
    mapped_trans, sting_intervals, _ = map_timeline_with_stings_and_cuts(trans_data, edit_data, total_duration)
    trans_segments = mapped_trans.get("segments", [])

    # Insert welcome sting speech segments (29.80s - 33.50s)
    welcome_segments = [
        {
            "start": 29.80,
            "end": 31.50,
            "text": "Welcome to the Deep Dive.",
            "words": [
                {"word": "Welcome", "start": 29.80, "end": 30.22},
                {"word": "to", "start": 30.22, "end": 30.50},
                {"word": "the", "start": 30.50, "end": 30.64},
                {"word": "Deep", "start": 30.64, "end": 30.86},
                {"word": "Dive.", "start": 30.86, "end": 31.40},
            ]
        },
        {
            "start": 31.60,
            "end": 33.50,
            "text": "I am Satosha and I am Satoshi.",
            "words": [
                {"word": "I", "start": 31.60, "end": 31.75},
                {"word": "am", "start": 31.75, "end": 31.90},
                {"word": "Satosha", "start": 31.90, "end": 32.35},
                {"word": "and", "start": 32.35, "end": 32.55},
                {"word": "I", "start": 32.55, "end": 32.70},
                {"word": "am", "start": 32.70, "end": 32.85},
                {"word": "Satoshi.", "start": 32.85, "end": 33.35},
            ]
        }
    ]
    trans_segments.extend(welcome_segments)
    trans_segments.sort(key=lambda x: x.get("start", 0))

    # 5. Partition timeline into chunks (8 chunks ~6.7 mins each)
    os.makedirs(TEMP_CHUNKS_DIR, exist_ok=True)
    num_chunks = 8
    chunk_dur = total_duration / num_chunks
    tasks = []

    for i in range(num_chunks):
        s_t = i * chunk_dur
        e_t = total_duration if i == num_chunks - 1 else (i + 1) * chunk_dur
        chunk_mp4 = os.path.join(TEMP_CHUNKS_DIR, f"chunk_{i:02d}.mp4")
        # Filter scenes overlapping this chunk with a small margin
        c_scenes = [s for s in scene_intervals if s["end"] >= s_t - 5.0 and s["start"] <= e_t + 5.0]
        tasks.append((i, s_t, e_t, chunk_mp4, trans_segments, c_scenes, fps))

    workers = min(4, cpu_count())
    print(f"Rendering {num_chunks} chunks in parallel across {workers} CPU workers...", flush=True)
    t0 = time.time()

    with Pool(processes=workers) as pool:
        chunk_outputs = pool.map(render_chunk_worker, tasks)

    t_render = time.time() - t0
    print(f"\nAll {num_chunks} chunks rendered in {t_render:.1f}s ({t_render/60:.2f} mins)!")

    # 6. Concatenate chunks and mux original master audio
    print("\nConcatenating chunks with FFmpeg concat demuxer & muxing master audio...")
    concat_list_path = os.path.join(TEMP_CHUNKS_DIR, "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for ch_path in chunk_outputs:
            safe_p = ch_path.replace("\\", "/")
            f.write(f"file '{safe_p}'\n")

    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-i", AUDIO_PATH,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        FINAL_MASTER_MP4
    ]

    res = subprocess.run(cmd_concat, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error during concat: {res.stderr}")
        return

    total_time = time.time() - t0
    fsize_mb = os.path.getsize(FINAL_MASTER_MP4) / (1024 * 1024)

    print("\n==================================================")
    print(f"SUCCESS: Longform Master Video Rendered!")
    print(f"Path: {FINAL_MASTER_MP4}")
    print(f"Total Duration: {total_duration/60:.2f} mins")
    print(f"Total Wall Time: {total_time:.1f}s ({total_time/60:.2f} mins)")
    print(f"File Size: {fsize_mb:.2f} MB")
    print(f"Scenes Composited: {len(scene_intervals)} Bespoke Manim MP4s")
    print("==================================================")

if __name__ == "__main__":
    main()
