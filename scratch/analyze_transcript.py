import json
import re

with open("transcription.json", "r", encoding="utf-8") as f:
    data = json.load(f)

segments = data.get("segments", [])
print(f"Total segments: {len(segments)}")

keywords = [
    "Copernicus", "Galileo", "Newton", "Lavoisier", "Darwin", "Maxwell", "Einstein",
    "Kuhn", "Laudan", "Swales", "Planck", "Equant", "Pisa", "vortices", "phlogiston",
    "displacement current", "relativity", "photoelectric"
]

keyword_matches = {kw: [] for kw in keywords}

for idx, seg in enumerate(segments):
    text = seg.get("text", "")
    start = seg.get("start")
    end = seg.get("end")
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
            keyword_matches[kw].append((idx, start, end, text.strip()))

for kw in keywords:
    matches = keyword_matches[kw]
    print(f"\n--- Matches for '{kw}' (Count: {len(matches)}) ---")
    # Print the first 5 matches to avoid too much output
    for m in matches[:10]:
        print(f"  Seg {m[0]} ({m[1]:.1f}s - {m[2]:.1f}s): {m[3]}")
    if len(matches) > 10:
        print(f"  ... and {len(matches) - 10} more matches.")
