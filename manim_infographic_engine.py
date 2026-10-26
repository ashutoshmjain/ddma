"""
manim_infographic_engine.py - Elegant Manim Pedagogy Engine for DDMA Short Clips
Renders 1080x1080 square vector animations based on Richard Feynman physical intuitions
and Tristan Needham geometric transformations, completely avoiding AI "Performance Theater".
"""

import os
import sys
import json
import subprocess
import tempfile
from typing import List, Dict, Any, Optional

# Manim Configuration for Native 1080x1080 Square Viewport
MANIM_HEADER = """
from manim import *

config.pixel_width = 1080
config.pixel_height = 1080
config.frame_width = 8.0
config.frame_height = 8.0
config.background_color = "#090E1A"
config.frame_rate = 30
"""

# Supported Pedagogical Archetypes
PEDAGOGICAL_ARCHETYPES = [
    "balance_scale",          # Fulcrum, trade-offs, revenue vs burn
    "leaky_bucket",           # Thermodynamic loss, inflow vs drainage
    "funnel_filter",          # Bottlenecks, selection, throughput compression
    "flywheel_gear",          # Compounding loops, rotational inertia, acceleration
    "network_artery",         # Interconnection, trade routes vs isolation fallacy
    "foundation_stack",       # Solid base vs fragile top layers
    "robot_unplugged",        # The physical robot fallacy (dead battery, missing plug)
    "circuit_switch",         # Logic gate, threshold barrier, state trigger
]


def generate_pedagogical_storyboard(
    clip_obj: Dict[str, Any],
    body_duration: float,
    intro_offset: float = 1.5,
    custom_instructions: str = "",
    genai_mod=None,
    force_regenerate: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generate or retrieve cached Feynman/Needham pedagogical scenes for a 2-3 min clip.
    Strictly follows the Pacing Rule (~2 animations per minute = 4-6 scenes total).
    """
    existing = clip_obj.get("infographic_scenes")
    if (
        existing
        and isinstance(existing, list)
        and len(existing) >= 3
        and not force_regenerate
        and not custom_instructions
    ):
        last_scene_end = float(existing[-1].get("end", 0.0))
        if abs(last_scene_end - float(body_duration)) <= 1.5:
            return existing

    title = clip_obj.get("title", "Deep Dive")
    chunks = clip_obj.get("caption_chunks") or []
    
    # Extract transcript text and word timestamps
    transcript_text = " ".join(ch.get("text", "") for ch in chunks) if chunks else clip_obj.get("text", "")

    # Calculate optimal scene count: ~25s per scene (2 animations per minute)
    num_scenes = max(3, min(6, int(round(body_duration / 25.0))))
    target_scene_dur = body_duration / float(num_scenes)

    scenes = None
    if genai_mod is not None:
        try:
            prompt = (
                f"You are a master scientific visualizer designing an educational Manim animation for a 2-3 minute video clip.\n"
                f"Topic: '{title}'. Total Clip Duration: {body_duration:.2f} seconds.\n\n"
                f"Transcript Dialogue:\n{transcript_text}\n\n"
                f"PEDAGOGICAL PRINCIPLES (The Feynman & Tristan Needham Standard):\n"
                f"1. AVOID 'Performance Theater': Do not suggest random floating numbers, spinning gears, or meaningless shapes.\n"
                f"2. Figurative Physical Metaphors: Every scene must use an everyday physical object (scale, leaking pipe, battery plug, trade road, funnel).\n"
                f"3. Strictly {num_scenes} continuous scenes (~{target_scene_dur:.1f}s each), from 0.0 to {body_duration:.2f}s.\n"
                f"Allowed archetypes: {', '.join(PEDAGOGICAL_ARCHETYPES)}\n"
                f"{('- Special instructions: ' + custom_instructions) if custom_instructions else ''}\n\n"
                f"Return ONLY a valid JSON array of {num_scenes} objects with schema:\n"
                f'[\n'
                f'  {{\n'
                f'    "start": 0.0,\n'
                f'    "end": {target_scene_dur:.1f},\n'
                f'    "archetype": "...",\n'
                f'    "title": "SHORT TITLE (1-3 WORDS)",\n'
                f'    "insight": "Core pedagogical insight in one sentence",\n'
                f'    "metaphor": "Concrete physical analogy (e.g. Robot running out of battery without wall plug)",\n'
                f'    "labels": ["LEFT_LABEL", "RIGHT_LABEL"]\n'
                f'  }}\n'
                f']'
            )
            for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    m = genai_mod.GenerativeModel(m_name)
                    res = m.generate_content(prompt)
                    raw = res.text.strip()
                    if "```json" in raw:
                        raw = raw.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw:
                        raw = raw.split("```")[1].split("```")[0].strip()
                    parsed = json.loads(raw)
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        scenes = parsed
                        break
                except Exception as m_err:
                    print(f"[Manim Engine] Gemini {m_name} attempt failed: {m_err}")
                    continue
        except Exception as e:
            print(f"[Manim Engine] AI storyboard generation failed: {e}")

    # Fallback heuristic storyboard if AI unavailable or invalid
    if not scenes or len(scenes) < 2:
        scenes = []
        archetype_cycle = [
            ("robot_unplugged", "ONTOLOGICAL FALLACY", "Confusing autonomy with total isolation", "Physical robot wandering with dead battery", ["ROBOT", "NO PLUG"]),
            ("balance_scale", "THE AUTONOMY FULCRUM", "Autonomy is balancing income against compute burn", "Mechanical fulcrum scale balancing satoshis vs electricity", ["BURN", "REVENUE"]),
            ("leaky_bucket", "THERMODYNAMIC LOSS", "Systems radiate entropy and must take in continuous fuel", "Reservoir leaking fluid with active replacement pump", ["ENTROPY", "INFLOW"]),
            ("network_artery", "INTERCONNECTED TRADE", "True independence requires external commercial arteries", "Node revived by high-speed trade connection", ["ISLAND", "NETWORK"]),
            ("funnel_filter", "THROUGHPUT FILTER", "Selection pressure separating viable systems from noise", "Aperture funnel concentrating high-signal flow", ["NOISE", "SIGNAL"])
        ]
        for i in range(num_scenes):
            s_t = round(i * target_scene_dur, 2)
            e_t = round(body_duration if i == num_scenes - 1 else (i + 1) * target_scene_dur, 2)
            arch, t_title, t_ins, t_met, t_labs = archetype_cycle[i % len(archetype_cycle)]
            scenes.append({
                "start": s_t,
                "end": e_t,
                "archetype": arch,
                "title": t_title,
                "insight": t_ins,
                "metaphor": t_met,
                "labels": t_labs
            })

    # Validate boundary alignment
    scenes[0]["start"] = 0.0
    for i in range(len(scenes) - 1):
        scenes[i + 1]["start"] = scenes[i]["end"]
    scenes[-1]["end"] = round(body_duration, 2)

    return scenes


def generate_manim_scene_python(scene_data: Dict[str, Any], scene_class_name: str, duration: float) -> str:
    """
    Generate Python Manim code for a single 1080x1080 scene adhering to
    the Feynman & Tristan Needham standard.
    """
    archetype = scene_data.get("archetype", "balance_scale")
    title_text = scene_data.get("title", "DEEP DIVE").upper()
    labels = scene_data.get("labels", ["STATE A", "STATE B"])
    lbl_a = labels[0] if len(labels) > 0 else "INPUT"
    lbl_b = labels[1] if len(labels) > 1 else "OUTPUT"

    # Micro-beat timings calculated from scene duration
    t_enter = min(1.2, duration * 0.15)
    t_stage1 = min(1.5, duration * 0.25)
    t_kinetic = min(2.0, duration * 0.35)
    t_hold = max(1.0, duration - (t_enter + t_stage1 + t_kinetic))

    if archetype == "balance_scale":
        code = f"""
class {scene_class_name}(Scene):
    def construct(self):
        # 1. Header
        title = Text("{title_text}", font="Arial", weight=BOLD, font_size=26, color="#F8FAFC")
        title.to_edge(UP, buff=0.6)
        rule = Line(LEFT * 2.8, RIGHT * 2.8, color="#00E5FF", stroke_width=3).next_to(title, DOWN, buff=0.15)
        self.play(FadeIn(title), Create(rule), run_time={t_enter:.2f})

        # 2. Fulcrum & Beam
        fulcrum = Polygon([-0.4, -1.2, 0], [0.4, -1.2, 0], [0, -0.6, 0], color="#64748B", fill_color="#334155", fill_opacity=1.0)
        beam = RoundedRectangle(corner_radius=0.08, height=0.16, width=5.4, color="#00E5FF", fill_color="#00E5FF", fill_opacity=1.0).move_to([0, -0.5, 0])
        self.play(FadeIn(fulcrum), GrowFromCenter(beam), run_time={t_stage1:.2f})

        # 3. Weights on Pans
        left_box = RoundedRectangle(corner_radius=0.12, height=1.1, width=1.6, color="#EF4444", fill_color="#1E1015", fill_opacity=0.9, stroke_width=4).move_to([-1.9, 0.15, 0])
        left_txt = Text("{lbl_a}", font="Arial", weight=BOLD, font_size=15, color="#FCA5A5").move_to(left_box.get_center())
        left_grp = VGroup(left_box, left_txt)

        right_box = RoundedRectangle(corner_radius=0.12, height=1.1, width=1.6, color="#10B981", fill_color="#0C1E14", fill_opacity=0.9, stroke_width=4).move_to([1.9, 0.15, 0])
        right_txt = Text("{lbl_b}", font="Arial", weight=BOLD, font_size=15, color="#86EFAC").move_to(right_box.get_center())
        right_grp = VGroup(right_box, right_txt)

        self.play(FadeIn(left_grp, shift=DOWN*0.4), FadeIn(right_grp, shift=DOWN*0.4), run_time={t_stage1:.2f})

        # 4. Kinetic Transformation: Weight shifts and fulcrum tilts
        self.play(
            Rotate(beam, angle=14 * DEGREES, about_point=[0, -0.6, 0]),
            left_grp.animate.shift(DOWN * 0.5 + RIGHT * 0.05),
            right_grp.animate.shift(UP * 0.5 + LEFT * 0.05),
            run_time={t_kinetic:.2f}
        )
        self.wait({t_hold:.2f})
"""
    elif archetype == "leaky_bucket":
        code = f"""
class {scene_class_name}(Scene):
    def construct(self):
        title = Text("{title_text}", font="Arial", weight=BOLD, font_size=26, color="#F8FAFC")
        title.to_edge(UP, buff=0.6)
        rule = Line(LEFT * 2.8, RIGHT * 2.8, color="#F59E0B", stroke_width=3).next_to(title, DOWN, buff=0.15)
        self.play(FadeIn(title), Create(rule), run_time={t_enter:.2f})

        # Reservoir Vessel
        p1, p2, p3, p4 = [-1.5, 1.0, 0], [-1.2, -1.5, 0], [1.2, -1.5, 0], [1.5, 1.0, 0]
        vessel = VMobject(color="#64748B", stroke_width=5).set_points_as_corners([p1, p2, p3, p4])
        water = Polygon([-1.1, -1.4, 0], [1.1, -1.4, 0], [1.25, 0.0, 0], [-1.25, 0.0, 0], color="#00E5FF", fill_color="#083344", fill_opacity=0.8, stroke_width=0)
        self.play(Create(vessel), FadeIn(water), run_time={t_stage1:.2f})

        # Inflow Pipe (Top) and Leak Drop (Bottom)
        inflow = Arrow(UP * 2.2, UP * 0.4, color="#10B981", stroke_width=6)
        in_lbl = Text("{lbl_b}", font="Arial", weight=BOLD, font_size=15, color="#86EFAC").next_to(inflow, RIGHT, buff=0.2)
        
        leak = Arrow(DOWN * 1.5, DOWN * 2.5, color="#EF4444", stroke_width=6)
        leak_lbl = Text("{lbl_a}", font="Arial", weight=BOLD, font_size=15, color="#FCA5A5").next_to(leak, RIGHT, buff=0.2)

        self.play(GrowArrow(inflow), FadeIn(in_lbl), GrowArrow(leak), FadeIn(leak_lbl), run_time={t_stage1:.2f})

        # Kinetic Pulse: Level adjusts
        self.play(water.animate.scale(1.15, about_point=[0, -1.4, 0]), run_time={t_kinetic:.2f})
        self.wait({t_hold:.2f})
"""
    elif archetype == "robot_unplugged":
        code = f"""
class {scene_class_name}(Scene):
    def construct(self):
        title = Text("{title_text}", font="Arial", weight=BOLD, font_size=26, color="#F8FAFC")
        title.to_edge(UP, buff=0.6)
        rule = Line(LEFT * 2.8, RIGHT * 2.8, color="#EF4444", stroke_width=3).next_to(title, DOWN, buff=0.15)
        self.play(FadeIn(title), Create(rule), run_time={t_enter:.2f})

        # Robot Silhouette / Head Core
        head = RoundedRectangle(corner_radius=0.2, height=1.8, width=2.0, color="#64748B", fill_color="#1E293B", fill_opacity=0.9, stroke_width=5).move_to([0, 0.3, 0])
        eye_l = Circle(radius=0.18, color="#00E5FF", fill_color="#00E5FF", fill_opacity=1.0).move_to([-0.5, 0.45, 0])
        eye_r = Circle(radius=0.18, color="#00E5FF", fill_color="#00E5FF", fill_opacity=1.0).move_to([0.5, 0.45, 0])
        robot = VGroup(head, eye_l, eye_r)

        # Hanging Loose Cord & Battery Gauge
        cord = CurvedArrow([0, -0.6, 0], [1.8, -1.8, 0], color="#F59E0B", stroke_width=6)
        plug = Rectangle(height=0.3, width=0.5, color="#F59E0B", fill_color="#F59E0B", fill_opacity=1.0).move_to([1.8, -1.8, 0])
        cord_grp = VGroup(cord, plug)

        batt_box = RoundedRectangle(corner_radius=0.08, height=0.5, width=1.4, color="#EF4444", stroke_width=3).move_to([0, -0.15, 0])
        batt_fill = Rectangle(height=0.36, width=0.3, color="#EF4444", fill_color="#EF4444", fill_opacity=1.0).move_to([-0.45, -0.15, 0])
        batt_txt = Text("EMPTY", font="Arial", weight=BOLD, font_size=12, color="#FCA5A5").next_to(batt_box, DOWN, buff=0.12)
        batt_grp = VGroup(batt_box, batt_fill, batt_txt)

        self.play(FadeIn(robot), run_time={t_stage1:.2f})
        self.play(Create(cord_grp), FadeIn(batt_grp), run_time={t_stage1:.2f})

        # Kinetic Flash: Eyes dim and cord swings searching
        self.play(
            eye_l.animate.set_color("#334155"),
            eye_r.animate.set_color("#334155"),
            cord_grp.animate.rotate(0.15, about_point=[0, -0.6, 0]),
            run_time={t_kinetic:.2f}
        )
        self.wait({t_hold:.2f})
"""
    elif archetype == "network_artery":
        code = f"""
class {scene_class_name}(Scene):
    def construct(self):
        title = Text("{title_text}", font="Arial", weight=BOLD, font_size=26, color="#F8FAFC")
        title.to_edge(UP, buff=0.6)
        rule = Line(LEFT * 2.8, RIGHT * 2.8, color="#10B981", stroke_width=3).next_to(title, DOWN, buff=0.15)
        self.play(FadeIn(title), Create(rule), run_time={t_enter:.2f})

        # Center Island Node
        center_node = Circle(radius=0.7, color="#00E5FF", fill_color="#083344", fill_opacity=0.9, stroke_width=5).move_to([0, -0.2, 0])
        center_lbl = Text("AUTONOMY", font="Arial", weight=BOLD, font_size=13, color="#F8FAFC").move_to(center_node.get_center())
        c_grp = VGroup(center_node, center_lbl)

        # 3 Satellite Network Hubs
        pos = [[-2.4, 0.8, 0], [2.4, 0.8, 0], [0, -2.1, 0]]
        nodes = []
        lines = []
        for p in pos:
            n = Circle(radius=0.45, color="#F59E0B", fill_color="#451A03", fill_opacity=0.9, stroke_width=4).move_to(p)
            l = Line(center_node.get_center(), n.get_center(), color="#334155", stroke_width=3)
            nodes.append(n)
            lines.append(l)

        self.play(FadeIn(c_grp), *[Create(l) for l in lines], *[FadeIn(n) for n in nodes], run_time={t_stage1:.2f})

        # Kinetic Pulse: High-speed trade pulse activates
        self.play(
            *[l.animate.set_color("#10B981").set_stroke(width=6) for l in lines],
            center_node.animate.set_color("#10B981"),
            run_time={t_kinetic:.2f}
        )
        self.wait({t_hold:.2f})
"""
    else:  # funnel_filter or default
        code = f"""
class {scene_class_name}(Scene):
    def construct(self):
        title = Text("{title_text}", font="Arial", weight=BOLD, font_size=26, color="#F8FAFC")
        title.to_edge(UP, buff=0.6)
        rule = Line(LEFT * 2.8, RIGHT * 2.8, color="#38BDF8", stroke_width=3).next_to(title, DOWN, buff=0.15)
        self.play(FadeIn(title), Create(rule), run_time={t_enter:.2f})

        # Funnel Aperture
        p1, p2, p3, p4 = [-2.2, 1.2, 0], [-0.5, -0.8, 0], [0.5, -0.8, 0], [2.2, 1.2, 0]
        funnel = VMobject(color="#64748B", stroke_width=5).set_points_as_corners([p1, p2, p3, p4])
        stem_l = Line([-0.5, -0.8, 0], [-0.5, -1.8, 0], color="#64748B", stroke_width=5)
        stem_r = Line([0.5, -0.8, 0], [0.5, -1.8, 0], color="#64748B", stroke_width=5)
        self.play(Create(funnel), Create(stem_l), Create(stem_r), run_time={t_stage1:.2f})

        # Particles Entering
        dots_in = VGroup(*[Circle(radius=0.12, color="#EF4444", fill_color="#EF4444", fill_opacity=1.0).move_to([x, 0.8, 0]) for x in [-1.6, -0.8, 0, 0.8, 1.6]])
        lbl_in = Text("{lbl_a}", font="Arial", weight=BOLD, font_size=14, color="#FCA5A5").next_to(dots_in, UP, buff=0.15)
        self.play(FadeIn(dots_in), FadeIn(lbl_in), run_time={t_stage1:.2f})

        # Kinetic Squeeze: Filtered beam exits
        out_arrow = Arrow([0, -0.8, 0], [0, -2.4, 0], color="#10B981", stroke_width=8)
        lbl_out = Text("{lbl_b}", font="Arial", weight=BOLD, font_size=14, color="#86EFAC").next_to(out_arrow, RIGHT, buff=0.2)
        self.play(GrowArrow(out_arrow), FadeIn(lbl_out), dots_in.animate.shift(DOWN * 0.8), run_time={t_kinetic:.2f})
        self.wait({t_hold:.2f})
"""
    return code


def render_manim_infographic_mp4(
    scenes: List[Dict[str, Any]],
    audio_path: str,
    out_mp4_path: str,
    duration: Optional[float] = None,
    fps: int = 30,
) -> str:
    """
    Compile full Manim educational script, render 1080x1080 MP4 scenes, and mux audio.
    """
    if duration is None or duration <= 0:
        try:
            p = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, timeout=10
            )
            if p.returncode == 0 and p.stdout.strip():
                duration = float(p.stdout.strip())
        except Exception:
            pass
    if not duration or duration <= 0:
        duration = scenes[-1]["end"] if scenes else 60.0

    os.makedirs(os.path.dirname(os.path.abspath(out_mp4_path)), exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="manim_ddma_")

    python_script_path = os.path.join(temp_dir, "render_scenes.py")
    scene_classes = []
    
    script_lines = [MANIM_HEADER]
    for idx, sc in enumerate(scenes):
        cls_name = f"PedagogicalScene{idx + 1}"
        scene_classes.append(cls_name)
        sc_dur = max(1.0, float(sc.get("end", 0.0)) - float(sc.get("start", 0.0)))
        code = generate_manim_scene_python(sc, cls_name, sc_dur)
        script_lines.append(code)

    with open(python_script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines))

    print(f"[Manim Engine] Compiling {len(scenes)} scenes to 1080x1080 via ManimCE...")
    
    rendered_clips = []
    for idx, cls_name in enumerate(scene_classes):
        out_sub_mp4 = os.path.join(temp_dir, f"scene_{idx + 1:02d}.mp4")
        # Run Manim directly
        cmd_manim = [
            sys.executable, "-m", "manim",
            "-qh",
            "--format=mp4",
            "-o", f"scene_{idx + 1:02d}.mp4",
            "--media_dir", temp_dir,
            python_script_path,
            cls_name
        ]
        res = subprocess.run(cmd_manim, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[Manim Engine] Warning rendering {cls_name}: {res.stderr}")
        
        # Locate generated MP4 in manim media_dir
        import glob
        matches = glob.glob(os.path.join(temp_dir, "videos", "**", f"scene_{idx + 1:02d}.mp4"), recursive=True)
        if matches and os.path.exists(matches[0]):
            rendered_clips.append(matches[0])
        else:
            print(f"[Manim Engine] Could not locate rendered output for {cls_name}")

    if not rendered_clips:
        raise Exception("Manim failed to render any scenes.")

    # Concat all scene MP4s and mux audio
    concat_list_path = os.path.join(temp_dir, "concat.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for c in rendered_clips:
            clean_p = c.replace("\\", "/")
            f.write(f"file '{clean_p}'\n")

    tmp_concat_mp4 = os.path.join(temp_dir, "stitched.mp4")
    cmd_stitch = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        tmp_concat_mp4
    ]
    subprocess.run(cmd_stitch, capture_output=True, text=True)

    # Final Mux with Audio Track
    cmd_mux = [
        "ffmpeg", "-y",
        "-i", tmp_concat_mp4,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{duration:.3f}",
        "-movflags", "+faststart",
        out_mp4_path
    ]
    proc_mux = subprocess.run(cmd_mux, capture_output=True, text=True)
    if proc_mux.returncode != 0:
        raise Exception(f"Final audio mux failed: {proc_mux.stderr}")

    print(f"[Manim Engine] Successfully generated 1080x1080 pedagogical infographic: {out_mp4_path}")
    return out_mp4_path
