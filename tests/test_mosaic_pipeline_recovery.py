"""
Unit and Regression Test Suite for Mosaic Pipeline Recovery & Prompt Settings Resilience.
Ensures:
1. Settings/prompt modifications dynamically load at runtime without crashing background processes.
2. Interrupted/zombie downloads and compilations (e.g. stuck at 95% due to server restarts) self-heal.
3. Prompt formatting and syntax rules remain intact.
"""

import os
import sys
import json
import time
import shutil
import unittest
from unittest.mock import patch, MagicMock

# Add scratch/ and root to sys.path so run_curator and ddma can be imported
DDMA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if DDMA_ROOT not in sys.path:
    sys.path.insert(0, DDMA_ROOT)
SCRATCH_DIR = os.path.join(DDMA_ROOT, "scratch")
if SCRATCH_DIR not in sys.path:
    sys.path.insert(0, SCRATCH_DIR)

from run_curator import (
    safe_load_json,
    load_settings,
    get_mosaic_default_prompt,
    build_mosaic_prompt_with_context,
    update_mosaic_job_state,
    load_mosaic_jobs,
    save_mosaic_jobs,
    heal_mosaic_project_state,
)


class TestMosaicPipelineRecovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(DDMA_ROOT, "scratch", "test_sandbox")
        os.makedirs(self.test_dir, exist_ok=True)
        self.orig_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_prompt_update_dynamic_loading(self):
        """Verifies that changing settings.json immediately updates prompt without caching or restart."""
        prompt_v1 = "PROMPT V1: Test motion graphics"
        prompt_v2 = "PROMPT V2: Updated Koe style instructions"

        # Write version 1
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump({"mosaic_default_prompt": prompt_v1}, f)

        loaded_v1 = get_mosaic_default_prompt()
        self.assertEqual(loaded_v1, prompt_v1)

        # Mutate settings to version 2 (simulating user edit)
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump({"mosaic_default_prompt": prompt_v2}, f)

        loaded_v2 = get_mosaic_default_prompt()
        self.assertEqual(loaded_v2, prompt_v2)

    def test_safe_load_json_resilience_to_missing_and_corrupt_files(self):
        """Verifies safe_load_json gracefully handles missing files and syntax glitches without raising."""
        # Non-existent file
        self.assertIsNone(safe_load_json("non_existent_file.json"))

        # Empty settings fallback
        settings = load_settings()
        self.assertEqual(settings, {})

        # Corrupt JSON file
        with open("corrupt.json", "w", encoding="utf-8") as f:
            f.write("{\"broken_json: unclosed")

        self.assertIsNone(safe_load_json("corrupt.json", retries=2, delay=0.01))

    def test_prompt_synthesis_structure(self):
        """Verifies synthesized prompt contains no orphaned brackets and includes full-timeline rules."""
        sample_prompt = (
            "MOTION DESIGN INSTRUCTIONS (YOUTUBE SHORTS)\n"
            "- Cover the entire timeline with ZERO blank frames.\n"
            "- Strong Outro: Final segment must conclude with active summary diagram."
        )
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump({"mosaic_default_prompt": sample_prompt}, f)

        full_prompt = build_mosaic_prompt_with_context(
            title="Meta Muse vs Apple PCC",
            transcript="Stateless versus stateful architectures in agentic AI."
        )

        self.assertIn("ZERO blank frames", full_prompt)
        self.assertIn("Strong Outro", full_prompt)
        self.assertIn("Meta Muse vs Apple PCC", full_prompt)
        # Ensure no accidental orphaned paste syntax remains
        self.assertNotIn("').", full_prompt)

    def test_self_healing_recovers_stuck_95_percent_job(self):
        """
        Regression test for Clip 247-11 bug:
        When a process was interrupted at 95% (downloaded from Mosaic, but master clip compile was interrupted),
        heal_mosaic_project_state must resume compile-clip and advance status to completed (100%).
        """
        project_id = "episode_999"
        proj_dir = os.path.join("projects", project_id)
        clips_dir = "clips"
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(clips_dir, exist_ok=True)

        clip_num = 1
        run_id = "test-run-uuid-1234"

        # Plan with mosaic_run_id
        plan = [{"num": clip_num, "title": "Test Clip", "mosaic_run_id": run_id}]
        with open(os.path.join(proj_dir, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f)

        # Simulate downloaded Mosaic file existing on disk
        mosaic_file = os.path.join(clips_dir, f"999-{clip_num}-mosaic-{run_id}.mp4")
        with open(mosaic_file, "wb") as f:
            f.write(b"MOCK_MOSAIC_VIDEO_DATA" * 200)

        # Simulate stuck job at 95%
        update_mosaic_job_state(project_id, clip_num, "downloading output", 95, run_id=run_id)
        jobs = load_mosaic_jobs(project_id)
        self.assertEqual(jobs[clip_num]["progress"], 95)
        self.assertEqual(jobs[clip_num]["status"], "downloading output")

        # Mock compile-clip execution
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            heal_mosaic_project_state(project_id, plan)
            # Give background thread up to 1 second to execute worker
            time.sleep(0.3)

        jobs_after = load_mosaic_jobs(project_id)
        self.assertEqual(jobs_after[clip_num]["status"], "completed")
        self.assertEqual(jobs_after[clip_num]["progress"], 100)

    def test_self_healing_syncs_already_compiled_master_clip(self):
        """
        Regression test:
        If master clip file already exists and ffprobe validates it, but mosaic_jobs.json
        was left at 95% due to process termination, heal_mosaic_project_state immediately marks 100%.
        """
        project_id = "episode_998"
        proj_dir = os.path.join("projects", project_id)
        clips_dir = "clips"
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(clips_dir, exist_ok=True)

        clip_num = 2
        run_id = "valid-run-uuid-5678"

        plan = [{"num": clip_num, "title": "Compiled Clip", "mosaic_run_id": run_id}]
        with open(os.path.join(proj_dir, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f)

        # Both mosaic file and master clip exist
        mosaic_file = os.path.join(clips_dir, f"998-{clip_num}-mosaic-{run_id}.mp4")
        master_file = os.path.join(clips_dir, f"998-{clip_num}.mp4")
        with open(mosaic_file, "wb") as f:
            f.write(b"MOSAIC_DATA" * 200)
        with open(master_file, "wb") as f:
            f.write(b"MASTER_DATA" * 200)

        # Set stuck job in disk json
        update_mosaic_job_state(project_id, clip_num, "downloading output", 95, run_id=run_id)

        # Mock ffprobe reporting duration=150.0 (valid video)
        with patch("subprocess.run") as mock_probe:
            mock_probe.return_value = MagicMock(returncode=0, stdout="duration=150.0")
            heal_mosaic_project_state(project_id, plan)

        jobs_after = load_mosaic_jobs(project_id)
        self.assertEqual(jobs_after[clip_num]["status"], "completed")
        self.assertEqual(jobs_after[clip_num]["progress"], 100)


if __name__ == "__main__":
    unittest.main()
