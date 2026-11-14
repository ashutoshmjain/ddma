"""
test_plan_clip0_title.py

ITEM 8: clip 0's title must come from the episode title, never the hardcoded
249 title. Exercises parse_spoken_cue_tripartite_plan directly with synthetic
spoken-cue segments:
1. episode_title given -> clips[0]["title"] == episode_title, other clips
   keep their own titles, bridge_text stays dynamic.
2. episode_title omitted -> generic fallback (2 words, within the intro
   <=3-word invariant), and NOT "What Exactly Is Reality?".
"""

import sys
import unittest
from pathlib import Path

DDMA_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(DDMA_DIR))

from ddma import parse_spoken_cue_tripartite_plan

EP_TITLE = "Test Episode Title"
HARDCODED_249 = "What Exactly Is Reality?"


def _seg(start, words, cue_at=None):
    """Build one segment; cue_at marks the index of the 'Clip' word."""
    text = " ".join(words)
    wlist = []
    t = float(start)
    for w in words:
        wlist.append({"word": w, "start": round(t, 2), "end": round(t + 0.4, 2)})
        t += 0.5
    return {"start": float(start), "end": round(t, 2), "text": text, "words": wlist}


def _fixture_transcription():
    segs = [
        _seg(0, ["Welcome", "to", "the", "show", "warmup", "chat", "tonight"]),
        _seg(21, ["And", "now", "Clip", "1", "begins", "the", "deep", "dive",
                  "into", "the", "topic", "at", "hand", "today"]),
        _seg(120, ["Moving", "on", "Clip", "2", "takes", "us", "deeper",
                   "into", "the", "second", "idea", "here"]),
        _seg(240, ["Finally", "Clip", "3", "wraps", "up", "with", "the",
                   "third", "and", "final", "point", "made"]),
        _seg(260, ["Thanks", "for", "listening", "to", "the", "show"]),
    ]
    return {"text": " ".join(s["text"] for s in segs), "segments": segs}


class TestPlanClip0Title(unittest.TestCase):

    def test_01_clip0_uses_episode_title(self):
        clips = parse_spoken_cue_tripartite_plan(
            _fixture_transcription(), episode_title=EP_TITLE)
        self.assertTrue(clips, "expected clips from spoken cues")
        c0 = next(c for c in clips if c["num"] == 0)
        self.assertEqual(
            c0["title"], EP_TITLE,
            f'clip 0 must carry the episode title, got {c0["title"]!r}',
        )
        # Other clips keep their own titles; bridge stays dynamic.
        others = [c for c in clips if c["num"] != 0]
        self.assertTrue(others, "expected clips beyond clip 0")
        for c in others:
            self.assertTrue(c["title"], f'clip {c["num"]} lost its title')
            self.assertNotEqual(c["title"], EP_TITLE)
        self.assertTrue(c0.get("bridge_text"), "clip 0 bridge_text missing")

    def test_02_no_title_falls_back_generic(self):
        clips = parse_spoken_cue_tripartite_plan(_fixture_transcription())
        self.assertTrue(clips, "expected clips from spoken cues")
        c0 = next(c for c in clips if c["num"] == 0)
        self.assertNotEqual(
            c0["title"], HARDCODED_249,
            "clip 0 must never fall back to another episode's title",
        )
        self.assertLessEqual(
            len(c0["title"].split()), 3,
            f'fallback title must fit the intro <=3-word invariant: {c0["title"]!r}',
        )


if __name__ == "__main__":
    unittest.main()
