import json
import os

def main():
    trans_file = "transcription.json"
    if not os.path.exists(trans_file):
        print(f"Error: {trans_file} not found.")
        return
        
    with open(trans_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    segments = data.get("segments", [])
    
    print("Transcript Segments between 2400s and 2630s:")
    print("--------------------------------------------------")
    for idx, s in enumerate(segments):
        start = s["start"]
        end = s["end"]
        if start >= 2400.0 and start <= 2630.0:
            print(f"Seg {idx} ({start:.2f}s -> {end:.2f}s): {s['text']}")

if __name__ == "__main__":
    main()
