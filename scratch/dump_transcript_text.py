import json

with open("transcription.json", "r", encoding="utf-8") as f:
    data = json.load(f)

segments = data.get("segments", [])

with open("scratch/transcript_dump.txt", "w", encoding="utf-8") as out:
    for s in segments:
        out.write(f"[{s['id']}] ({s['start']:.2f}s - {s['end']:.2f}s): {s['text'].strip()}\n")

print(f"Dumped {len(segments)} segments to scratch/transcript_dump.txt")
