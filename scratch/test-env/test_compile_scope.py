"""
test_compile_scope.py (Issue 68)

Compile-scope regression test: `ddma.py compile-clip --num N` must produce
one clip (plan duration + 1.5s intro + 5s outro), never a full-episode-length
video, and must leave the plan's source `duration` for that clip unchanged.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

DDMA_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(DDMA_DIR))

from ddma import get_project_canonical_audio_path


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, f"ffprobe failed: {out.stderr}"
    return float(out.stdout.strip())


class TestCompileScope(unittest.TestCase):

    def test_01_compile_clip_8_stays_clip_scoped(self):
        project_id = "episode_249"
        num = 8
        plan_path = DDMA_DIR / "projects" / project_id / "plan.json"
        clips_dir = DDMA_DIR / "clips"

        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        clip = next(c for c in plan if c.get("num") == num)
        exp_dur = round(float(clip["end"]) - float(clip["start"]), 2)
        self.assertAlmostEqual(exp_dur, 81.44, places=1)

        audio_file = get_project_canonical_audio_path(
            str(DDMA_DIR / "projects" / project_id), project_id)
        self.assertTrue(audio_file and os.path.exists(audio_file))

        cut_cmd = [sys.executable, "ddma.py", "cut",
                   "--audio", audio_file,
                   "--plan-file", str(plan_path),
                   "--out-dir", str(clips_dir),
                   "--num", str(num)]
        res_cut = subprocess.run(cut_cmd, capture_output=True, text=True,
                                 cwd=str(DDMA_DIR))
        self.assertEqual(res_cut.returncode, 0,
                         f"ddma cut failed: {res_cut.stderr}")

        cmd = [sys.executable, "ddma.py", "compile-clip",
               "--num", str(num),
               "--plan-file", str(plan_path),
               "--source", "mosaic"]
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True,
                             cwd=str(DDMA_DIR))
        wall = time.time() - t0
        combined = res.stdout + res.stderr
        print(f"\n[Scope] compile-clip wall time: {wall:.1f}s")
        self.assertEqual(res.returncode, 0,
                         f"compile-clip failed: {res.stderr[-2000:]}")

        mux_lines = [l for l in combined.splitlines()
                     if "Preserving Mosaic motion graphics video track from" in l]
        print("[Scope] mux line: " + (mux_lines[-1] if mux_lines else "NONE (black-canvas draft)"))
        self.assertNotIn(
            "exceeds the 180s", combined,
            "180s ceiling warning must not appear for a single clip compile")

        # The scope contract is against cut's slice (speech span + the clip's
        # own sting tail), not the raw [start, end] span: assembly adds
        # 1.5s intro + 5s outro minus ~1s of crossfade overlap (~+5.5s).
        slice_files = [p for p in clips_dir.glob(f"249-{num}-*.mp3")
                       if not p.name.startswith("podcast_")]
        slice_files += [p for p in clips_dir.glob(f"249-{num}.mp3")
                        if not p.name.startswith("podcast_")]
        self.assertTrue(slice_files, "cut must leave a clip-scoped slice")
        slice_dur = ffprobe_duration(
            max(slice_files, key=lambda p: p.stat().st_mtime))
        print(f"[Scope] cut slice: {slice_dur:.2f}s "
              f"(clip speech span {exp_dur:.2f}s)")
        expected_total = slice_dur + 5.5

        out_mp4 = clips_dir / f"249-{num}.mp4"
        self.assertTrue(out_mp4.exists(), f"{out_mp4} must exist")
        got_dur = ffprobe_duration(out_mp4)
        print(f"[Scope] output duration: {got_dur:.2f}s "
              f"(expected ~{expected_total:.2f}s)")
        self.assertLess(got_dur, 180.0,
                        f"output {got_dur:.2f}s breaches the 180s ceiling")
        self.assertLess(abs(got_dur - expected_total), 2.0,
                        f"output {got_dur:.2f}s is not clip-scoped "
                        f"(expected ~{expected_total:.2f}s)")

        self.assertLess(wall, 600.0,
                        f"single-clip compile took {wall:.0f}s, expected well under 10 minutes")

        plan_after = json.loads(plan_path.read_text(encoding="utf-8"))
        clip_after = next(c for c in plan_after if c.get("num") == num)
        self.assertEqual(clip_after.get("duration"), exp_dur,
                         f"plan duration must stay {exp_dur}, "
                         f"got {clip_after.get('duration')}")


class TestExactMatchOnly(unittest.TestCase):
    """Cross-episode glob fallbacks removed: exact-match only, refuse loudly.

    Fixture episode_997 lives in /tmp (out of the repo): clip 10 is locked
    with no usable [start, end], the tmp master dir holds an exact dummy
    master plus ANOTHER episode's real slice as the decoy, and the real
    ddma/clips dir (full of other episodes' slices) is the audio dir.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ddma_exact_997_"))
        cls.proj = cls.tmp / "episode_997"
        cls.proj.mkdir()
        plan = [{"num": 10, "title": "T10", "locked": True,
                 "segments": []}]
        (cls.proj / "plan.json").write_text(json.dumps(plan),
                                            encoding="utf-8")
        # Canonical continuous audio, so the slice lookup (not the
        # canonical-audio check) is what refuses below.
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "anullsrc=r=48000:cl=stereo", "-t", "1",
             str(cls.proj / "997.m4a")],
            capture_output=True, check=True)
        # Exact dummy master for the fixture clip ...
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "color=black:s=1080x1920:d=1", "-pix_fmt", "yuv420p",
             str(cls.tmp / "997-10.mp4")],
            capture_output=True, check=True)
        # ... plus another episode's real slice as the decoy the old
        # cross-episode fallback would silently have taken.
        shutil.copy(DDMA_DIR / "clips" / "245-10-DNA to folded proteins.mp3",
                    cls.tmp / "245-10-DNA to folded proteins.mp3")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_02_mux_refuses_other_episode_audio(self):
        cmd = [sys.executable, "ddma.py", "mux-clip",
               "--num", "10",
               "--plan-file", str(self.proj / "plan.json"),
               "--audio-dir", str(DDMA_DIR / "clips"),
               "--out-dir", str(self.tmp)]
        res = subprocess.run(cmd, capture_output=True, text=True,
                             cwd=str(DDMA_DIR), timeout=120)
        combined = res.stdout + res.stderr
        print(f"\n[Exact] mux-clip returncode: {res.returncode}")
        self.assertNotEqual(res.returncode, 0,
                            "mux-clip must refuse without an exact-match slice")
        self.assertIn("No audio file found", combined,
                      "mux-clip must fail loudly naming the missing audio, "
                      f"not take 245's slice. Output: {combined[-800:]}")

    def test_03_compile_refuses_other_episode_slice(self):
        cmd = [sys.executable, "ddma.py", "compile-clip",
               "--num", "10",
               "--plan-file", str(self.proj / "plan.json"),
               "--master-dir", str(self.tmp),
               "--out-dir", str(self.tmp),
               "--source", "mosaic"]
        res = subprocess.run(cmd, capture_output=True, text=True,
                             cwd=str(DDMA_DIR), timeout=180)
        combined = res.stdout + res.stderr
        print(f"\n[Exact] compile-clip returncode: {res.returncode}")
        self.assertNotEqual(res.returncode, 0,
                            "compile-clip must refuse without an exact-match slice")
        self.assertIn("refusing full-episode audio", combined,
                      "compile-clip must hit the loud slice refusal, "
                      f"not take 245's slice. Output: {combined[-800:]}")


if __name__ == "__main__":
    unittest.main()
