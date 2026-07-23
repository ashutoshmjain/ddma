import os
import subprocess
import whisper

def transcribe_file(video_path):
    print(f"Transcribing {video_path}...")
    audio_path = video_path.replace(".mp4", "_extracted.wav")
    try:
        # Extract audio using ffmpeg
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        # Load whisper model
        model = whisper.load_model("tiny.en")
        result = model.transcribe(audio_path)
        
        return result["text"]
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

if __name__ == "__main__":
    out_lines = []
    
    for clip_num in (13, 14):
        video_path = f"clips/244-{clip_num}-original.mp4"
        if os.path.exists(video_path):
            text = transcribe_file(video_path)
            out_lines.append(f"=== Clip {clip_num} Gold Video Transcription ===")
            out_lines.append(text)
            out_lines.append("")
        else:
            out_lines.append(f"=== Clip {clip_num} Gold Video NOT FOUND ===")
            
    with open("scratch/transcribe_gold.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print("Done!")
