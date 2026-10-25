import os
import av
from PIL import Image

MODULE_03_MANIM_SCENES = [
    {"num": 1, "start": 835.0, "end": 865.0, "title": "PERISHABLE INVENTORY // ARROW OF TIME"},
    {"num": 2, "start": 865.0, "end": 893.8, "title": "THE DIGITAL JAR FALLACY"},
    {"num": 3, "start": 893.8, "end": 922.5, "title": "PERISHABLE ASSET VS UTILITY"},
    {"num": 4, "start": 922.5, "end": 952.5, "title": "GEOGRAPHIC MONOPOLY VS SPOT MARKET"},
    {"num": 5, "start": 952.5, "end": 983.8, "title": "ZERO BRAND LOYALTY // GLADIATOR ARENA"},
    {"num": 6, "start": 983.8, "end": 1013.6, "title": "ALGORITHMIC YIELD MANAGEMENT"},
    {"num": 7, "start": 1013.6, "end": 1042.0, "title": "THE $1.50 BLUNT INSTRUMENT"},
    {"num": 8, "start": 1042.0, "end": 1072.0, "title": "CONTINUOUS YIELD OPTIMIZATION"},
    {"num": 9, "start": 1072.0, "end": 1101.9, "title": "PEAK SURGE & MIDNIGHT CITY"},
    {"num": 10, "start": 1101.9, "end": 1131.0, "title": "MARGINAL COST FLOOR // CLUB HYPERION"},
    {"num": 11, "start": 1131.0, "end": 1161.0, "title": "TIER 1: HIGH-SPEED TRADING BOTS"},
    {"num": 12, "start": 1161.0, "end": 1190.0, "title": "TIER 3: STANDBY BATCH FORKLIFT"},
    {"num": 13, "start": 1190.0, "end": 1220.0, "title": "DISEMBODIED INTELLIGENCE KEYS"},
    {"num": 14, "start": 1220.0, "end": 1248.6, "title": "WEIGHTS MATRIX & EMPTY IT DESK"},
    {"num": 15, "start": 1248.6, "end": 1278.0, "title": "MCP & THE CYBER BOUNCER"},
    {"num": 16, "start": 1278.0, "end": 1307.0, "title": "HANDING CONTROLS TO AI GATEWAY"},
    {"num": 17, "start": 1307.0, "end": 1336.5, "title": "OPERATIONAL SOVEREIGNTY OUROBOROS"},
    {"num": 18, "start": 1336.5, "end": 1350.0, "title": "HOMEOSTATIC GOVERNANCE"},
]

class ManimSceneReader:
    def __init__(self, scenes_config=None, rendered_dir="scratch/manim_module_03/rendered", fps=25):
        self.scenes = scenes_config or MODULE_03_MANIM_SCENES
        self.rendered_dir = rendered_dir
        self.fps = fps
        self.current_num = None
        self.container = None
        self.stream = None
        self.last_img = None
        self.cur_frame_idx = -1

    def get_scene_for_time(self, t):
        for sc in self.scenes:
            if sc["start"] <= t < sc["end"]:
                return sc
        if self.scenes:
            if t >= self.scenes[-1]["end"]:
                return self.scenes[-1]
            return self.scenes[0]
        return None

    def get_frame(self, t):
        active_sc = self.get_scene_for_time(t)
        if not active_sc:
            return self.last_img or Image.new("RGB", (1920, 860), (8, 12, 20))

        num = active_sc["num"]
        if num != self.current_num:
            if self.container:
                try:
                    self.container.close()
                except Exception:
                    pass
            self.current_num = num
            path = os.path.join(self.rendered_dir, f"scene_{num:02d}.mp4")
            if os.path.exists(path):
                try:
                    self.container = av.open(path)
                    self.stream = self.container.streams.video[0]
                    self.cur_frame_idx = -1
                except Exception as e:
                    print(f"Error opening {path}: {e}")
                    self.container = None
                    self.stream = None
            else:
                self.container = None
                self.stream = None

        if not self.container:
            return self.last_img or Image.new("RGB", (1920, 860), (8, 12, 20))

        local_t = max(0.0, t - active_sc["start"])
        target_f_idx = int(round(local_t * self.fps))

        if target_f_idx == self.cur_frame_idx and self.last_img is not None:
            return self.last_img

        try:
            if target_f_idx < self.cur_frame_idx:
                self.container.seek(0)
                self.cur_frame_idx = -1

            for frame in self.container.decode(self.stream):
                self.cur_frame_idx += 1
                if self.cur_frame_idx >= target_f_idx:
                    self.last_img = frame.to_image()
                    return self.last_img
        except Exception:
            pass

        return self.last_img or Image.new("RGB", (1920, 860), (8, 12, 20))

    def close(self):
        if self.container:
            try:
                self.container.close()
            except Exception:
                pass
            self.container = None
