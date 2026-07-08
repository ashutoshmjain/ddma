import json
import os
import subprocess
import shutil

def run_cmd(cmd):
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"Error executing command: {res.stderr}")
        raise Exception(f"FFmpeg command failed: {res.stderr}")
    return res

def get_sting_path(music_file):
    if not music_file or music_file == "none":
        return None
    music_dir = "music"
    if os.path.exists(music_dir):
        for f in os.listdir(music_dir):
            if music_file.lower() in f.lower() or f.lower() in music_file.lower():
                return os.path.join(music_dir, f)
    return None

def main():
    plan_file = "plan.json"
    audio_source = "244.m4a"
    final_mp3 = "combined_244.mp3"
    
    if not os.path.exists(plan_file):
        print(f"Error: {plan_file} not found. Use Curator UI to create a plan first.")
        return
        
    if not os.path.exists(audio_source):
        print(f"Error: Audio source {audio_source} not found.")
        return
        
    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    print(f"Starting final audio compilation for {len(plan)} clips from plan.json...")
    
    # Extract all segments across all clips in chronological order
    all_segments = []
    for c_idx, clip in enumerate(plan):
        title = clip.get("title", f"Clip #{c_idx+1}")
        segments = clip.get("segments", [])
        print(f"Clip #{c_idx+1}: '{title}' with {len(segments)} segments.")
        for seg in segments:
            all_segments.append(seg)
            
    if not all_segments:
        print("Error: No segments found to compile.")
        return
        
    print(f"\nTotal segments to compile: {len(all_segments)}")
    
    temp_wav_files = []
    try:
        for idx, seg in enumerate(all_segments):
            temp_file = f"temp_final_seg_{idx}.wav"
            temp_wav_files.append(temp_file)
            
            if seg["type"] == "audio":
                start = seg["start"]
                end = seg["end"]
                print(f"  [{idx+1}/{len(all_segments)}] Slicing Speech: {start}s -> {end}s")
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-to", str(end),
                    "-i", audio_source,
                    "-ar", "48000",
                    "-ac", "2",
                    temp_file
                ]
                run_cmd(cmd)
            elif seg["type"] == "music":
                music_file = seg["music_file"]
                duration = seg["duration"]
                sting_path = get_sting_path(music_file)
                print(f"  [{idx+1}/{len(all_segments)}] Slicing Music: '{music_file}' ({duration}s)")
                
                if not sting_path:
                    # Generate digital silence
                    cmd = [
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-i", f"anullsrc=r=48000:cl=stereo:d={duration}",
                        temp_file
                    ]
                    run_cmd(cmd)
                else:
                    # Slice music and scale volume down
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", sting_path,
                        "-t", str(duration),
                        "-ar", "48000",
                        "-ac", "2",
                        "-af", "volume=0.35",
                        temp_file
                    ]
                    run_cmd(cmd)
                    
        # Concatenate all segments
        print(f"\nConcatenating {len(temp_wav_files)} segments into final audio...")
        if len(temp_wav_files) == 1:
            cmd_concat = [
                "ffmpeg", "-y",
                "-i", temp_wav_files[0],
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                final_mp3
            ]
            run_cmd(cmd_concat)
        else:
            cmd_concat = ["ffmpeg", "-y"]
            for tf in temp_wav_files:
                cmd_concat += ["-i", tf]
                
            filter_complex = "".join(f"[{i}:a]" for i in range(len(temp_wav_files)))
            filter_complex += f"concat=n={len(temp_wav_files)}:v=0:a=1[out]"
            
            cmd_concat += [
                "-filter_complex", filter_complex,
                "-map", "[out]",
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                final_mp3
            ]
            run_cmd(cmd_concat)
            
        print(f"\nSUCCESS! Compiled final narration audio to: {final_mp3}")
        
    finally:
        # Cleanup temporary wav files
        print("Cleaning up temporary segment files...")
        for tf in temp_wav_files:
            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except:
                    pass

if __name__ == "__main__":
    main()
