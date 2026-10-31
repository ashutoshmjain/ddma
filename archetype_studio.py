import os
import sys
import re
import json
import glob
import time
import shutil
import subprocess
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GITHUB_ROOT = os.path.dirname(SCRIPT_DIR)
ARCHETYPES_DIR = os.path.join(SCRIPT_DIR, "archetypes")
MEDIA_VIDEOS_DIR = os.path.join(GITHUB_ROOT, "media", "videos")
SETTINGS_PATH = os.path.join(SCRIPT_DIR, "settings.json")
GENERATED_ARCHETYPES_JSON = os.path.join(SCRIPT_DIR, "generated_archetypes.json")

PRIMARY_MODELS = [
    "models/gemini-3.5-flash-lite",
    "models/gemini-flash-lite-latest",
    "models/gemini-3.5-flash",
]


def _load_api_key() -> Optional[str]:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                key = json.load(f).get("gemini_api_key")
                if key:
                    return str(key).strip()
        except Exception:
            pass
    return os.environ.get("GEMINI_API_KEY")


def extract_scene_classes_from_py(py_path: str) -> List[Dict[str, Any]]:
    """
    Parses a clip_XX_gemini_scenes.py file and returns ordered scene class blocks
    with their class name, source code, extracted title/category, and visual comments.
    """
    if not os.path.exists(py_path):
        return []
    with open(py_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(r"(^class\s+(Scene\w+)\s*\([^\)]*\):)", re.MULTILINE)
    matches = list(pattern.finditer(content))
    results = []
    for i, m in enumerate(matches):
        start_idx = m.start()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        cls_name = m.group(2)
        cls_code = content[start_idx:end_idx].strip()

        # Extract human-readable summary / metaphor from comments or title call
        comments = []
        for line in cls_code.splitlines():
            s = line.strip()
            if s.startswith("#") and "Title and Footer" not in s and "Using universal" not in s:
                comments.append(s.lstrip("# ").strip())

        title_match = re.search(r'get_footer_and_title\([^\"]*\"([^\"]+)\"(?:,\s*\"([^\"]+)\")?', cls_code)
        if not title_match:
            title_match = re.search(r'Text\(\s*\"([^\"]+)\"', cls_code)

        scene_title = title_match.group(1) if title_match else cls_name
        cat_match = re.search(r'get_footer(?:_and_title)?\([^\)]*\"([^\"]+)\"\s*\)', cls_code)
        category = cat_match.group(1) if cat_match else "AI AUTONOMY"

        results.append({
            "class_name": cls_name,
            "title": scene_title,
            "category": category,
            "visual_summary": " • ".join(comments[:3]) if comments else "Bespoke monochrome vector animation",
            "code": cls_code,
        })
    return results


def ensure_clip_meta(clip_num: int, plan_clip: Optional[Dict[str, Any]] = None, body_duration: Optional[float] = None) -> Dict[str, Any]:
    """
    Loads or synthesizes clip_XX_meta.json aligned with clip_XX_gemini_scenes.py and media/videos/clip_XX_gemini_scenes/740p15/*.mp4.
    Returns both absolute episode timestamps and clip-relative timestamps (rel_start, rel_end, video_start, video_end).
    """
    c_num = int(clip_num)
    py_path = os.path.join(ARCHETYPES_DIR, f"clip_{c_num:02d}_gemini_scenes.py")
    meta_path = os.path.join(ARCHETYPES_DIR, f"clip_{c_num:02d}_meta.json")
    video_dir = os.path.join(MEDIA_VIDEOS_DIR, f"clip_{c_num:02d}_gemini_scenes", "740p15")

    parsed_classes = extract_scene_classes_from_py(py_path)

    meta_data = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
        except Exception:
            meta_data = {}

    raw_beats = meta_data.get("beats", [])

    # Determine clip start/end and spoken words from plan_clip if available
    if plan_clip is None:
        # Auto-discover plan_clip from projects/episode_248/plan.json or root plan.json so we NEVER lose caption_chunks or audio_duration!
        for cand_plan in [
            os.path.join(SCRIPT_DIR, "projects", "episode_248", "plan.json"),
            os.path.join(SCRIPT_DIR, "plan.json"),
        ]:
            if os.path.exists(cand_plan):
                try:
                    with open(cand_plan, "r", encoding="utf-8") as pf:
                        p_list = json.load(pf)
                    if isinstance(p_list, list):
                        plan_clip = next((c for c in p_list if str(c.get("num")) == str(c_num)), None)
                        if plan_clip:
                            break
                except Exception:
                    pass

    c_start = float(plan_clip.get("start", 0.0)) if plan_clip else (float(raw_beats[0]["start"]) if raw_beats else 0.0)
    c_end = float(plan_clip.get("end", c_start + 120.0)) if plan_clip else (float(raw_beats[-1]["end"]) if raw_beats else c_start + 120.0)
    plan_audio_dur = float(plan_clip.get("audio_duration") or 0.0) if plan_clip else 0.0
    eff_body_dur = (
        float(body_duration)
        if body_duration and body_duration > 0
        else (plan_audio_dur if plan_audio_dur > 0 else max(10.0, c_end - c_start))
    )

    n_scenes = len(parsed_classes)
    if n_scenes == 0:
        return {"clip_num": c_num, "title": plan_clip.get("title", f"Part {c_num}") if plan_clip else f"Part {c_num}", "beats": []}

    # Extract caption words or chunks from plan_clip to populate exact spoken transcript per beat
    caption_chunks = (plan_clip.get("caption_chunks") or []) if plan_clip else []
    full_clip_text = (plan_clip.get("text") or "") if plan_clip else ""

    intro_offset = 1.5  # DDMA compiled short has a 1.5s intro title card before body starts
    beat_dur = eff_body_dur / n_scenes

    enriched_beats = []
    for idx, cls_info in enumerate(parsed_classes):
        cls_name = cls_info["class_name"]
        mp4_path = os.path.join(video_dir, f"{cls_name}.mp4")
        raw_b = raw_beats[idx] if idx < len(raw_beats) else {}

        rel_start = round(idx * beat_dur, 2)
        rel_end = round(eff_body_dur if idx == n_scenes - 1 else (idx + 1) * beat_dur, 2)
        vid_start = round(intro_offset + rel_start, 2)
        vid_end = round(intro_offset + rel_end, 2)

        abs_start = float(raw_b.get("start", c_start + rel_start))
        abs_end = float(raw_b.get("end", c_start + rel_end))

        # ALWAYS compute spoken text from exact word-timed caption_chunks in [vid_start, vid_end] when available
        # so the right-hand "SPOKEN DIALOGUE IN THIS BEAT" matches the burned-in ASS captions 100%!
        b_text = ""
        if caption_chunks:
            beat_words = []
            for ch in caption_chunks:
                w_list = ch.get("words") or []
                if w_list:
                    for w_obj in w_list:
                        w_mid = 0.5 * (float(w_obj.get("start", 0.0)) + float(w_obj.get("end", 0.0)))
                        if vid_start <= w_mid < vid_end:
                            beat_words.append(str(w_obj.get("word", "")).strip())
                else:
                    ch_mid = 0.5 * (float(ch.get("start", 0.0)) + float(ch.get("end", 0.0)))
                    if vid_start <= ch_mid < vid_end:
                        beat_words.append(str(ch.get("text", "")).strip())
            if beat_words:
                b_text = " ".join(w for w in beat_words if w)

        if not b_text:
            b_text = str(raw_b.get("text", "")).strip()
        if (not b_text or b_text.startswith("Discussion on ")) and full_clip_text:
            words = full_clip_text.split()
            w_per_beat = max(1, len(words) // n_scenes)
            b_text = " ".join(words[idx * w_per_beat : (idx + 1) * w_per_beat])

        # Always prefer the latest visual_summary extracted from the live Python class comments
        live_summary = cls_info.get("visual_summary") or raw_b.get("visual_summary") or "Bespoke monochrome vector animation"

        enriched_beats.append({
            "index": idx + 1,
            "class_name": cls_name,
            "title": raw_b.get("title") or cls_info["title"],
            "category": raw_b.get("category") or cls_info["category"],
            "visual_summary": live_summary,
            "user_notes": raw_b.get("user_notes", ""),
            "start": round(abs_start, 2),
            "end": round(abs_end, 2),
            "rel_start": rel_start,
            "rel_end": rel_end,
            "video_start": vid_start,
            "video_end": vid_end,
            "duration": round(rel_end - rel_start, 2),
            "text": b_text,
            "mp4_exists": os.path.exists(mp4_path),
            "mp4_url": f"/media/videos/clip_{c_num:02d}_gemini_scenes/740p15/{cls_name}.mp4",
            "py_file": f"archetypes/clip_{c_num:02d}_gemini_scenes.py",
            "code": cls_info["code"],
        })

    out_meta = {
        "clip_num": c_num,
        "title": (plan_clip.get("title") if plan_clip else None) or meta_data.get("title", f"Part {c_num}"),
        "py_file": f"archetypes/clip_{c_num:02d}_gemini_scenes.py",
        "video_dir": f"media/videos/clip_{c_num:02d}_gemini_scenes/740p15",
        "intro_offset": intro_offset,
        "body_duration": round(eff_body_dur, 2),
        "beats": enriched_beats,
    }

    # Save enriched metadata back to clip_XX_meta.json (without duplicating full code in JSON)
    disk_beats = []
    for b in enriched_beats:
        b_copy = dict(b)
        b_copy.pop("code", None)
        disk_beats.append(b_copy)
    disk_meta = dict(out_meta)
    disk_meta["beats"] = disk_beats
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(disk_meta, f, indent=2)
    except Exception:
        pass

    return out_meta


def stitch_precompiled_archetypes_for_clip(
    clip_num: int,
    audio_path: str,
    out_mp4_path: str,
    body_duration: float,
    plan_clip: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Super-fast (< 3 seconds) assembler for a DDMA short clip body video (740x740 with masked bottom title
    and centered graphic alignment between the captions line and bottom footer line)
    using the pre-compiled Manim MP4s in media/videos/clip_XX_gemini_scenes/740p15/*.mp4!
    Automatically compiles any missing single scene if needed.
    """
    c_num = int(clip_num)
    meta = ensure_clip_meta(c_num, plan_clip=plan_clip, body_duration=body_duration)
    beats = meta.get("beats", [])
    if not beats:
        return False

    video_dir = os.path.join(MEDIA_VIDEOS_DIR, f"clip_{c_num:02d}_gemini_scenes", "740p15")
    os.makedirs(video_dir, exist_ok=True)

    mp4_paths = []
    for b in beats:
        cls_name = b["class_name"]
        mp4_p = os.path.join(video_dir, f"{cls_name}.mp4")
        if not os.path.exists(mp4_p):
            compile_single_scene(c_num, cls_name)
        if os.path.exists(mp4_p):
            mp4_paths.append((mp4_p, float(b["duration"])))

    if not mp4_paths:
        return False

    os.makedirs(os.path.dirname(os.path.abspath(out_mp4_path)), exist_ok=True)

    # Build a single FFmpeg filtergraph that:
    # 1. Masks out y=622..672 (removing any legacy bottom archetype title while preserving footer at y=672..740),
    # 2. Shifts the illustration zone (y=110..622) upward by 110px to y=0..512 (padded with black down to y=672)
    #    so the graphic is centered midway between the upper captions line and the bottom footer line!
    # 3. Normalizes each scene to its beat duration, concatenates them seamlessly, and muxes the clip audio!
    inputs = []
    filter_parts = []
    concat_inputs = []

    for i, (mp4_p, t_dur) in enumerate(mp4_paths):
        inputs.extend(["-i", mp4_p])
        sc_dur = t_dur
        try:
            p = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", mp4_p],
                capture_output=True, text=True, timeout=5
            )
            if p.returncode == 0 and p.stdout.strip():
                sc_dur = float(p.stdout.strip())
        except Exception:
            pass

        pad_dur = max(0.0, t_dur - sc_dur + 0.5)
        filter_parts.append(
            f"[{i}:v]scale=740:740,fps=25,drawbox=x=0:y=622:w=740:h=50:color=black:t=fill,split=2[g{i}][f{i}];"
            f"[g{i}]crop=740:512:0:110,pad=740:672:0:0:black[gp{i}];"
            f"[f{i}]crop=740:68:0:672[fp{i}];"
            f"[gp{i}][fp{i}]vstack=inputs=2,"
            f"tpad=stop_mode=clone:stop_duration={pad_dur:.2f},trim=duration={t_dur:.3f},setpts=PTS-STARTPTS[v{i}];"
        )
        concat_inputs.append(f"[v{i}]")

    audio_idx = len(mp4_paths)
    inputs.extend(["-i", audio_path])

    filter_complex = (
        "".join(filter_parts)
        + "".join(concat_inputs)
        + f"concat=n={len(mp4_paths)}:v=1:a=0,setsar=1[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", f"{audio_idx}:a:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{body_duration:.3f}",
        "-movflags", "+faststart",
        out_mp4_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ArchetypeStudio] Warning stitching clip {c_num}: {res.stderr[-400:]}")
        return False

    print(f"[ArchetypeStudio] Superfast stitched {len(mp4_paths)} pre-compiled archetypes -> {out_mp4_path}")
    return True


def compile_single_scene(clip_num: int, class_name: str) -> Tuple[bool, str]:
    """
    Compiles a single Manim Scene class inside ddma/archetypes/clip_XX_gemini_scenes.py
    and places the resulting 740x740 MP4 into media/videos/clip_XX_gemini_scenes/740p15/<class_name>.mp4.
    """
    c_num = int(clip_num)
    py_path = os.path.join(ARCHETYPES_DIR, f"clip_{c_num:02d}_gemini_scenes.py")
    if not os.path.exists(py_path):
        return False, f"Scene file {py_path} not found."

    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{ARCHETYPES_DIR}{os.pathsep}{existing_pp}" if existing_pp else ARCHETYPES_DIR

    cmd = [
        sys.executable, "-m", "manim", "render",
        "-r", "740,740",
        "--fps", "15",
        "--format", "mp4",
        "--media_dir", os.path.join(GITHUB_ROOT, "media"),
        py_path,
        class_name,
    ]
    res = subprocess.run(cmd, cwd=GITHUB_ROOT, env=env, capture_output=True, text=True)
    out_mp4 = os.path.join(MEDIA_VIDEOS_DIR, f"clip_{c_num:02d}_gemini_scenes", "740p15", f"{class_name}.mp4")

    # Purge partial_movie_files immediately so disk stays clean
    partial_dir = os.path.join(MEDIA_VIDEOS_DIR, f"clip_{c_num:02d}_gemini_scenes", "740p15", "partial_movie_files", class_name)
    if os.path.exists(partial_dir):
        shutil.rmtree(partial_dir, ignore_errors=True)

    if res.returncode == 0 and os.path.exists(out_mp4):
        return True, out_mp4
    return False, (res.stderr or res.stdout)[-600:]


def synthesize_figurative_manim_class(
    class_name: str,
    user_directive: str,
    spoken_text: str = "",
    duration: float = 7.5,
) -> str:
    """
    Synthesizes bespoke, error-free pure monochrome ManimCE Python code locally
    when the Gemini REST API is unavailable or returns HTTP 401/429.
    Supports literal figurative animations (commercial airplane flying with empty seats,
    faucet dripping, forklift, server rack + clock, balance scale, battery/plug, etc.)
    centered cleanly in the middle of the viewport.
    """
    combined = f"{user_directive} {spoken_text}".lower()
    d_clean = user_directive.strip().replace('"', "'") if user_directive.strip() else "Figurative concept animation"
    dur = max(4.0, float(duration))

    # 1. Commercial Airplane Flying (with empty cabin windows & passing clouds)
    if any(k in combined for k in ["airplane", "plane", "flight", "flying", "jet", "airline", "aircraft", "empty seat"]):
        t_build = round(min(1.6, dur * 0.16), 2)
        t_fly = round(max(2.0, dur - t_build - 0.8), 2)
        t_out = round(max(0.5, dur - t_build - t_fly), 2)
        return f'''class {class_name}(Scene):
    def construct(self):
        get_footer(self)
        # Visual: Commercial airplane flying past clouds with empty cabin seats ({d_clean})
        fuselage = RoundedRectangle(width=3.6, height=0.82, corner_radius=0.41, color="#FFFFFF", stroke_width=4, fill_color="#000000", fill_opacity=1.0).move_to([0, -0.35, 0])
        nose_cockpit = Arc(radius=0.38, start_angle=-PI/3, angle=2*PI/3, color="#FFFFFF", stroke_width=3).move_to([1.52, -0.32, 0])
        tail_fin = Polygon([-1.65, 0.0, 0], [-2.25, 1.05, 0], [-1.15, 0.0, 0], color="#FFFFFF", stroke_width=4, fill_color="#000000", fill_opacity=1.0)
        wing_bottom = Polygon([-0.55, -0.45, 0], [-1.35, -1.55, 0], [-0.25, -1.55, 0], [0.55, -0.45, 0], color="#FFFFFF", stroke_width=4, fill_color="#000000", fill_opacity=1.0)
        wing_top = Polygon([-0.35, 0.05, 0], [-0.95, 0.78, 0], [-0.15, 0.78, 0], [0.35, 0.05, 0], color="#FFFFFF", stroke_width=3, fill_color="#000000", fill_opacity=1.0)
        engine = RoundedRectangle(width=0.65, height=0.30, corner_radius=0.12, color="#FFFFFF", stroke_width=3, fill_color="#FFFFFF", fill_opacity=0.18).move_to([-0.5, -1.12, 0])

        # Illuminated empty passenger windows along the cabin
        windows = VGroup(*[
            RoundedRectangle(width=0.22, height=0.26, corner_radius=0.06, color="#FFFFFF", stroke_width=2.5, fill_color="#FFFFFF", fill_opacity=0.15).move_to([-1.05 + i * 0.44, -0.32, 0])
            for i in range(6)
        ])
        tag = Text("EMPTY SEATS • PERISHABLE CAPACITY", font="Arial", weight=BOLD, font_size=12, color="#FFFFFF").move_to([0, -2.05, 0]).set_opacity(0.85)

        plane = VGroup(wing_top, tail_fin, fuselage, nose_cockpit, windows, wing_bottom, engine).shift(LEFT * 0.4 + DOWN * 0.15)

        # Fluffy clouds & slipstream lines rushing past
        cloud1 = VGroup(
            Circle(radius=0.28, color="#FFFFFF", stroke_width=2.5, fill_color="#000000", fill_opacity=1.0).move_to([2.1, 0.85, 0]),
            Circle(radius=0.36, color="#FFFFFF", stroke_width=2.5, fill_color="#000000", fill_opacity=1.0).move_to([2.45, 0.92, 0]),
            Circle(radius=0.26, color="#FFFFFF", stroke_width=2.5, fill_color="#000000", fill_opacity=1.0).move_to([2.8, 0.82, 0]),
        ).set_opacity(0.75)
        cloud2 = VGroup(
            Circle(radius=0.24, color="#FFFFFF", stroke_width=2.5, fill_color="#000000", fill_opacity=1.0).move_to([2.5, -1.55, 0]),
            Circle(radius=0.32, color="#FFFFFF", stroke_width=2.5, fill_color="#000000", fill_opacity=1.0).move_to([2.85, -1.48, 0]),
        ).set_opacity(0.65)
        wind_lines = VGroup(
            DashedLine([3.2, 0.35, 0], [-3.2, 0.35, 0], color="#FFFFFF", stroke_width=2).set_opacity(0.45),
            DashedLine([3.2, -0.95, 0], [-3.2, -0.95, 0], color="#FFFFFF", stroke_width=2).set_opacity(0.45),
        )

        self.play(FadeIn(plane, shift=RIGHT * 0.4 + UP * 0.15), FadeIn(cloud1), FadeIn(cloud2), Create(wind_lines), FadeIn(tag), run_time={t_build})
        self.play(
            plane.animate.shift(RIGHT * 0.85 + UP * 0.32).rotate(0.06),
            cloud1.animate.shift(LEFT * 4.4),
            cloud2.animate.shift(LEFT * 4.8),
            windows.animate.set_fill(opacity=0.45),
            run_time={t_fly},
            rate_func=linear
        )
        self.wait({t_out})'''

        # 2. 100 Meter Sprint / Race Against Time (Sprinter on track racing a giant stopwatch to finish line)
    if any(k in combined for k in ["100 meter", "race", "sprint", "runner", "running", "track", "marathon", "finish line"]):
        t_build = round(min(1.6, dur * 0.16), 2)
        t_run = round(max(2.0, dur - t_build - 0.8), 2)
        t_out = round(max(0.5, dur - t_build - t_run), 2)
        return f'''class {class_name}(Scene):
    def construct(self):
        get_footer(self)
        # Visual: 100-meter sprinter racing against a ticking stopwatch toward the finish line ({d_clean})
        track_top = Line([-3.1, -0.85, 0], [3.1, -0.85, 0], color="#FFFFFF", stroke_width=3).set_opacity(0.6)
        track_mid = DashedLine([-3.1, -1.35, 0], [3.1, -1.35, 0], color="#FFFFFF", stroke_width=2).set_opacity(0.45)
        track_bot = Line([-3.1, -1.85, 0], [3.1, -1.85, 0], color="#FFFFFF", stroke_width=4)
        finish_pole = Line([2.55, 0.25, 0], [2.55, -1.85, 0], color="#FFFFFF", stroke_width=4)
        finish_banner = RoundedRectangle(width=1.05, height=0.34, corner_radius=0.05, color="#FFFFFF", stroke_width=2.5, fill_color="#000000", fill_opacity=1.0).move_to([2.55, 0.45, 0])
        finish_txt = Text("100M", font="Arial", weight=BOLD, font_size=12, color="#FFFFFF").move_to(finish_banner.get_center())

        # Ticking Stopwatch above the track
        clock_ring = Circle(radius=0.58, color="#FFFFFF", stroke_width=3.5).move_to([0.0, 0.45, 0])
        clock_btn = Rectangle(width=0.22, height=0.12, color="#FFFFFF", fill_color="#FFFFFF", fill_opacity=1.0).next_to(clock_ring, UP, buff=0.02)
        clock_hand = Line(clock_ring.get_center(), clock_ring.get_center() + UP * 0.44, color="#FFFFFF", stroke_width=4)

        # Dynamic Sprinter Figure (Head, Torso, Pumping Arms & Striding Legs)
        r_head = Circle(radius=0.18, color="#FFFFFF", stroke_width=3.5, fill_color="#FFFFFF", fill_opacity=0.2).move_to([-2.0, -0.15, 0])
        r_torso = Line([-2.05, -0.33, 0], [-2.25, -0.95, 0], color="#FFFFFF", stroke_width=5)
        r_arm_f = Line([-2.12, -0.52, 0], [-1.72, -0.38, 0], color="#FFFFFF", stroke_width=3.5)
        r_arm_b = Line([-2.12, -0.52, 0], [-2.52, -0.68, 0], color="#FFFFFF", stroke_width=3.5)
        r_leg_f = Line([-2.25, -0.95, 0], [-1.82, -1.55, 0], color="#FFFFFF", stroke_width=4)
        r_leg_b = Line([-2.25, -0.95, 0], [-2.65, -1.52, 0], color="#FFFFFF", stroke_width=4)
        speed_lines = VGroup(
            Line([-3.0, -0.35, 0], [-2.45, -0.35, 0], color="#FFFFFF", stroke_width=2.5).set_opacity(0.6),
            Line([-3.1, -0.75, 0], [-2.55, -0.75, 0], color="#FFFFFF", stroke_width=2.5).set_opacity(0.6),
        )
        sprinter = VGroup(r_head, r_torso, r_arm_f, r_arm_b, r_leg_f, r_leg_b, speed_lines)
        tag = Text("100M SPRINT • RACE AGAINST TIME", font="Arial", weight=BOLD, font_size=12, color="#FFFFFF").move_to([0, -2.25, 0]).set_opacity(0.85)

        self.play(
            Create(track_top), Create(track_mid), Create(track_bot),
            Create(finish_pole), FadeIn(finish_banner), FadeIn(finish_txt),
            Create(clock_ring), FadeIn(clock_btn), Create(clock_hand),
            FadeIn(sprinter, shift=RIGHT * 0.3), FadeIn(tag),
            run_time={t_build}
        )
        self.play(
            sprinter.animate.shift(RIGHT * 4.15),
            Rotate(clock_hand, angle=-6 * PI, about_point=clock_ring.get_center()),
            finish_banner.animate.set_fill(color="#FFFFFF", opacity=0.25),
            run_time={t_run},
            rate_func=linear
        )
        self.wait({t_out})'''

    # 3. Check if directive matches any of our 22 cached figurative archetypes in generated_archetypes.json
    if os.path.exists(GENERATED_ARCHETYPES_JSON):
        try:
            with open(GENERATED_ARCHETYPES_JSON, "r", encoding="utf-8") as f:
                arch_cache = json.load(f)
            keyword_map = {
                "faucet": "leaky_faucet_meter",
                "drip": "leaky_faucet_meter",
                "ice cream": "melting_ice_cream_cone",
                "melt": "melting_ice_cream_cone",
                "forklift": "warehouse_forklift_stacker",
                "crate": "warehouse_forklift_stacker",
                "bouncer": "velvet_rope_bouncer",
                "velvet": "velvet_rope_bouncer",
                "puppet": "ornate_puppet_theater",
                "marionette": "ornate_puppet_theater",
                "locomotive": "coal_locomotive_burner",
                "train": "coal_locomotive_burner",
                "coal": "coal_locomotive_burner",
                "boiler": "steam_boiler_piston",
                "piston": "steam_boiler_piston",
                "tin can": "tin_can_intercom",
                "vault": "open_library_vault",
                "library": "open_library_vault",
                "bubble": "mayfly_bubble_blower",
                "parrot": "parrot_megaphone",
                "megaphone": "parrot_megaphone",
                "lighthouse": "lighthouse_storm_waves",
            }
            chosen_key = None
            for kw, ak in keyword_map.items():
                if kw in combined and ak in arch_cache:
                    chosen_key = ak
                    break
            if chosen_key:
                raw_cls = arch_cache[chosen_key]
                idx = raw_cls.find("class CLASS_NAME_PLACEHOLDER")
                if idx != -1:
                    cls_body = raw_cls[idx:].replace("CLASS_NAME_PLACEHOLDER", class_name).replace("TITLE_TEXT_PLACEHOLDER", "")
                    cls_body = re.sub(r'title\s*=\s*Text\([^\)]*\)[^\n]*\n', 'title = VGroup()\n', cls_body)
                    return cls_body
        except Exception:
            pass

    # 3. General Kinetic Figurative Scene Builder for any custom producer directive
    t_build = round(min(1.6, dur * 0.2), 2)
    t_act = round(max(2.0, dur - t_build - 0.8), 2)
    t_out = round(max(0.5, dur - t_build - t_act), 2)
    short_label = " ".join(user_directive.upper().split()[:4]) if user_directive.strip() else "CONCEPT MODEL"
    short_label = re.sub(r'[^A-Z0-9 •\-]', '', short_label)[:28]

    return f'''class {class_name}(Scene):
    def construct(self):
        get_footer(self)
        # Visual: {d_clean}
        outer_frame = RoundedRectangle(width=4.4, height=2.6, corner_radius=0.18, color="#FFFFFF", stroke_width=4, fill_color="#000000", fill_opacity=1.0).move_to([0, -0.35, 0])
        core_hub = Circle(radius=0.72, color="#FFFFFF", stroke_width=5, fill_color="#FFFFFF", fill_opacity=0.15).move_to([-1.05, -0.35, 0])
        target_node = RoundedRectangle(width=1.3, height=1.3, corner_radius=0.15, color="#FFFFFF", stroke_width=4, fill_color="#FFFFFF", fill_opacity=0.12).move_to([1.15, -0.35, 0])
        flow_arrow = Arrow(core_hub.get_right(), target_node.get_left(), buff=0.15, color="#FFFFFF", stroke_width=6)
        orbit_dot = Circle(radius=0.14, color="#FFFFFF", fill_color="#FFFFFF", fill_opacity=1.0).move_to(core_hub.get_top())
        caption_lbl = Text("{short_label}", font="Arial", weight=BOLD, font_size=13, color="#FFFFFF").move_to([0, -2.05, 0]).set_opacity(0.85)

        scene_grp = VGroup(outer_frame, core_hub, target_node, flow_arrow, orbit_dot, caption_lbl)
        self.play(Create(outer_frame), FadeIn(core_hub), FadeIn(target_node), GrowArrow(flow_arrow), FadeIn(orbit_dot), FadeIn(caption_lbl), run_time={t_build})
        self.play(
            Rotate(orbit_dot, angle=4*PI, about_point=core_hub.get_center()),
            target_node.animate.set_fill(opacity=0.45).scale(1.08),
            run_time={t_act},
            rate_func=linear
        )
        self.wait({t_out})'''


def update_single_scene_with_ai(
    clip_num: int,
    beat_index: int,
    class_name: str,
    user_directive: str,
    spoken_text: str = "",
    duration: float = 7.5,
    custom_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Either saves direct custom Manim code or prompts Gemini Flash Lite (with automatic
    local figurative synthesizer fallback if the API key is an expired OAuth token)
    to rewrite ONLY the specified Scene class (`class_name`) inside
    `ddma/archetypes/clip_XX_gemini_scenes.py` based on `user_directive` and `spoken_text`,
    compiles just that single scene (~3s), and updates `clip_XX_meta.json`!
    Because it updates `ddma/archetypes/clip_XX_gemini_scenes.py` and `media/videos/clip_XX_gemini_scenes/740p15/`,
    both the Short Clip and the next Longform Master Video render automatically inherit the improvement!
    """
    c_num = int(clip_num)
    py_path = os.path.join(ARCHETYPES_DIR, f"clip_{c_num:02d}_gemini_scenes.py")
    meta_path = os.path.join(ARCHETYPES_DIR, f"clip_{c_num:02d}_meta.json")
    if not os.path.exists(py_path):
        raise Exception(f"Archetype file not found: {py_path}")

    with open(py_path, "r", encoding="utf-8") as f:
        full_py = f.read()

    # Locate the target class block in clip_XX_gemini_scenes.py
    pattern = re.compile(r"(^class\s+(Scene\w+)\s*\([^\)]*\):)", re.MULTILINE)
    matches = list(pattern.finditer(full_py))
    target_match_idx = next((i for i, m in enumerate(matches) if m.group(2) == class_name), None)
    if target_match_idx is None:
        raise Exception(f"Class {class_name} not found in {py_path}")

    start_pos = matches[target_match_idx].start()
    end_pos = matches[target_match_idx + 1].start() if target_match_idx + 1 < len(matches) else len(full_py)
    current_cls_code = full_py[start_pos:end_pos].strip()

    new_cls_code = custom_code.strip() if custom_code and custom_code.strip() else ""

    if not new_cls_code:
        api_key = _load_api_key()
        gen_text = ""

        # Only call generativelanguage.googleapis.com if api_key is a valid AIza... API key
        if api_key and not api_key.startswith("AQ."):
            prompt = f"""You are an elite Manim Community Edition (ManimCE) Python developer.
Rewrite ONLY the single Manim Scene class `{class_name}` below according to the Producer's Creative Change Request.

STRICT VISUAL & TECHNICAL RULES:
1. Class definition MUST remain exact: `class {class_name}(Scene):`
2. PURE MONOCHROME WHITE-ON-BLACK: Every stroke, line, and fill is pure shining white ("#FFFFFF") on pure black ("#000000"). ZERO other colors.
3. NO ARCHETYPE TITLES: Do NOT draw a big title at the top or bottom. Call `get_footer(self)` at the start of `construct(self)`.
4. SAFE ILLUSTRATION ZONE: Keep all geometry centered within x in [-3.0, 3.0] and y in [-1.8, 0.8] so it sits cleanly in the middle of the viewport.
5. SUPER DUMB & LITERAL FIGURATIVE STORYTELLING: Draw clear, bold figurative objects (3px-6px strokes) that immediately illustrate the Producer's request and spoken words. Include a `# Visual: <description>` comment at the top of `construct(self)`.
6. TIMING & PERSISTENCE INVARIANT: Total `run_time` + `self.wait()` must equal approximately {duration:.1f} seconds. NEVER call `FadeOut` on the main illustration at the end of the scene! The final visual state MUST persist on screen (`self.wait(...)`) until the next beat takes over so the screen is NEVER empty!
7. Use only standard ManimCE primitives: Line, DashedLine, Circle, Rectangle, RoundedRectangle, Polygon, Triangle, Arc, Arrow, DoubleArrow, Text, VGroup, Create, Write, FadeIn, GrowFromCenter, Transform, Rotate.

SPOKEN TRANSCRIPT DURING THIS {duration:.1f}s BEAT:
"{spoken_text}"

CURRENT MANIM CLASS CODE:
```python
{current_cls_code}
```

PRODUCER'S CREATIVE CHANGE REQUEST / FEEDBACK:
"{user_directive}"

Return ONLY the valid Python code for `class {class_name}(Scene):` inside a ```python ... ``` block. Do not include imports or other classes."""

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.35},
            }
            headers = {"Content-Type": "application/json"}
            for model_name in PRIMARY_MODELS:
                url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(req, timeout=35) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                    gen_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    if gen_text:
                        break
                except Exception as e:
                    print(f"[ArchetypeStudio] [{model_name}] error: {e}")
                    time.sleep(0.5)

        if gen_text:
            code_match = re.search(r"```(?:python)?\s*(class\s+" + re.escape(class_name) + r"[\s\S]*?)```", gen_text)
            if code_match:
                new_cls_code = code_match.group(1).strip()
            else:
                idx_c = gen_text.find(f"class {class_name}")
                if idx_c != -1:
                    new_cls_code = gen_text[idx_c:].replace("```", "").strip()

        # Automatic Local Figurative Manim Synthesizer fallback if REST API key is an OAuth token or unavailable
        if not new_cls_code:
            print(f"[ArchetypeStudio] Synthesizing bespoke figurative Manim class locally for {class_name}: '{user_directive}'")
            new_cls_code = synthesize_figurative_manim_class(
                class_name=class_name,
                user_directive=user_directive,
                spoken_text=spoken_text,
                duration=duration,
            )

    # Backup original code in memory so we can rollback if Manim fails to compile
    updated_full_py = full_py[:start_pos] + new_cls_code + "\n\n" + full_py[end_pos:]
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(updated_full_py)

    ok, msg = compile_single_scene(c_num, class_name)
    if not ok:
        # If Gemini returned code with a syntax/Manim error, try our guaranteed local figurative synthesizer before rolling back!
        if not custom_code:
            fallback_code = synthesize_figurative_manim_class(
                class_name=class_name,
                user_directive=user_directive,
                spoken_text=spoken_text,
                duration=duration,
            )
            updated_full_py = full_py[:start_pos] + fallback_code + "\n\n" + full_py[end_pos:]
            with open(py_path, "w", encoding="utf-8") as f:
                f.write(updated_full_py)
            ok2, msg2 = compile_single_scene(c_num, class_name)
            if ok2:
                new_cls_code = fallback_code
                ok = True

    if not ok:
        # Rollback so we never leave broken code in the library
        with open(py_path, "w", encoding="utf-8") as f:
            f.write(full_py)
        raise Exception(f"Manim compilation failed for updated {class_name} (rolled back safely):\n{msg}")

    # Persist user_notes / visual_summary in clip_XX_meta.json
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                m_data = json.load(f)
            for b in m_data.get("beats", []):
                if b.get("class_name") == class_name or b.get("index") == beat_index:
                    if user_directive:
                        b["user_notes"] = user_directive
                        b["visual_summary"] = f"Visual: {user_directive}"
                    b["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(m_data, f, indent=2)
        except Exception:
            pass

    return {
        "success": True,
        "clip_num": c_num,
        "class_name": class_name,
        "code": new_cls_code,
        "mp4_url": f"/media/videos/clip_{c_num:02d}_gemini_scenes/740p15/{class_name}.mp4?t={int(time.time())}",
    }
