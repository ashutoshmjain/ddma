"""
test_canonical_audio_compile.py

Focused regression tests for the canonical-audio contract in ddma.py:
1. get_project_canonical_audio_path (the ddma.py copy) prefers .m4a over .mp3
   and refuses mastered podcast_<ep>.mp3 files.
2. get_project_canonical_audio_path returns None when only a mastered
   podcast_<ep>.mp3 exists.
3. compile_clip refuses (exit 1, no silent Mosaic-audio fallback) on an
   episode with only a mastered .mp3.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DDMA_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(DDMA_DIR))

from ddma import get_project_canonical_audio_path


class TestCanonicalAudioCompile(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="canonical_audio_"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)

    def _project(self, name, files):
        proj = self.tmp / name
        proj.mkdir(parents=True, exist_ok=True)
        for fname in files:
            (proj / fname).write_bytes(b"\x00")
        return proj

    def test_01_m4a_preferred_over_mp3(self):
        """Invariant: .m4a wins over any .mp3, including a mastered podcast mp3."""
        proj = self._project("episode_994", ["994.m4a", "podcast_994.mp3", "994.mp3"])
        resolved = get_project_canonical_audio_path(str(proj), "episode_994")
        self.assertIsNotNone(resolved, "expected canonical audio to resolve")
        self.assertTrue(
            resolved.endswith("994.m4a"),
            f"expected 994.m4a to be preferred, got {resolved}",
        )

    def test_02_none_when_only_mastered_mp3(self):
        """Invariant: an episode with only podcast_<ep>.mp3 resolves to None."""
        proj = self._project("episode_995", ["podcast_995.mp3"])
        resolved = get_project_canonical_audio_path(str(proj), "episode_995")
        self.assertIsNone(
            resolved,
            f"expected None for mastered-only project, got {resolved}",
        )

    def test_03_compile_clip_refuses_mastered_only(self):
        """Invariant: compile_clip exits 1 (no silent fallback) with no canonical audio."""
        proj = self._project("episode_996", ["podcast_996.mp3"])
        (proj / "plan.json").write_text(json.dumps([{"num": 0, "title": "T0"}]))
        clips_dir = self.tmp / "clips_996"
        clips_dir.mkdir(exist_ok=True)
        (clips_dir / "996-0.mp4").write_bytes(b"\x00" * 1024)
        out_dir = self.tmp / "out_996"
        out_dir.mkdir(exist_ok=True)

        cmd = [
            sys.executable, "ddma.py", "compile-clip",
            "--num", "0",
            "--plan-file", str(proj / "plan.json"),
            "--master-dir", str(clips_dir),
            "--out-dir", str(out_dir),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DDMA_DIR))
        combined = (res.stdout + res.stderr).lower()
        self.assertNotEqual(
            res.returncode, 0,
            f"compile_clip must refuse a mastered-only episode: {res.stdout} {res.stderr}",
        )
        self.assertIn(
            "canonical", combined,
            f"refusal must name the canonical-audio cause: {res.stdout} {res.stderr}",
        )
        self.assertEqual(
            list(out_dir.iterdir()), [],
            f"no output may be produced on refusal, found {list(out_dir.iterdir())}",
        )


if __name__ == "__main__":
    unittest.main()
