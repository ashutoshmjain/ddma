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
    
    print("Transcript Segments between 1130s and 1380s:")
    print("--------------------------------------------------")
    for idx, s in enumerate(segments):
        start = s["start"]
        end = s["end"]
        if start >= 1130.0 and start <= 1380.0:
            print(f"Seg {idx} ({start:.2f}s -> {end:.2f}s): {s['text']}")

if __name__ == "__main__":
    main()
