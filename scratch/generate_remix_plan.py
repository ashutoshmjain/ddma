import json
import os
import glob

def find_closest_segment_idx(target_time, segments):
    closest_idx = 0
    min_diff = float('inf')
    for idx, seg in enumerate(segments):
        diff = abs(seg['start'] - target_time)
        if diff < min_diff:
            min_diff = diff
            closest_idx = idx
    return closest_idx

def main():
    plan_file = "remix_plan.json"
    transcription_file = "transcription.json"
    
    if not os.path.exists(transcription_file):
        print(f"Error: {transcription_file} not found.")
        return
        
    with open(transcription_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    segments = data.get("segments", [])
    
    # 19 Standalone Clips in the exact compiled order (No filler chatters!)
    # Format: (start_sec, end_sec, type, title, theme, sound_mood, sfx_name)
    rough_blocks = [
        # 1. Einstein Hook
        (2477.24, 2633.56, "standalone_clip", "Einstein's Magnet-Conductor Paradox", "Einstein", "Intrigue", "none"),
        # 2. Galileo Hook
        (1183.24, 1341.50, "standalone_clip", "The Tied Stones Paradox", "Galileo", "Analytical", "typing"),
        # 3. Intro
        (0.0, 110.43, "standalone_clip", "The Demolition Myth", "Introduction", "Intrigue", "none"),
        # 4. Epistemology
        (134.32, 215.73, "standalone_clip", "The Rigidness of Paradigms", "Epistemology", "Intrigue", "none"),
        (240.0, 361.64, "standalone_clip", "Laudan's Problems", "Epistemology", "Intrigue", "none"),
        (506.28, 598.80, "standalone_clip", "Planck's Principle", "Epistemology", "Demolition/Rupture", "none"),
        # 5. Copernicus
        (615.20, 737.64, "standalone_clip", "The Copernican Myth", "Copernicus", "Intrigue", "none"),
        (790.54, 920.32, "standalone_clip", "Ptolemy's Equant Cheat", "Copernicus", "Analytical", "typing"),
        # 6. Newton
        (1369.52, 1491.48, "standalone_clip", "Cartesian Vortices", "Newton", "Intrigue", "none"),
        # 7. Lavoisier
        (1640.56, 1734.80, "standalone_clip", "The Phlogiston Anomaly", "Lavoisier", "Intrigue", "none"),
        (1752.13, 1863.36, "standalone_clip", "The Analytical Balance", "Lavoisier", "Analytical", "typing"),
        # 8. Darwin
        (1920.22, 2012.75, "standalone_clip", "The Special Creation Doctrine", "Darwin", "Intrigue", "none"),
        (2028.72, 2110.16, "standalone_clip", "Darwin's Homology Proofs", "Darwin", "Analytical", "typing"),
        # 9. Maxwell
        (2278.18, 2403.49, "standalone_clip", "The Displacement Current", "Maxwell", "Analytical", "typing"),
        # 10. Einstein Photoelectric
        (2620.80, 2743.62, "standalone_clip", "The Photoelectric Paradox", "Einstein", "Analytical", "typing"),
        # 11. Cosmology/OPH
        (2890.92, 3003.24, "standalone_clip", "Observer Patch Holography", "Cosmology", "Intrigue", "none"),
        (3144.46, 3269.44, "standalone_clip", "OPH: Quantum, Time and de Sitter", "Cosmology", "Analytical", "typing"),
        (3461.26, 3587.62, "standalone_clip", "OPH: Black Holes, Dark Matter, and Laws", "Cosmology", "Analytical", "typing"),
        # 12. Conclusion
        (3676.32, 3799.54, "standalone_clip", "Tearing Down the Scaffold", "Conclusion", "Demolition/Rupture", "none")
    ]
    
    # Get all stings in music directory
    music_dir = "music"
    music_files = sorted([f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav"))])
    print(f"Found {len(music_files)} custom music stings in '{music_dir}'.")
    
    remix_plan = []
    
    for idx, item in enumerate(rough_blocks):
        r_start, r_end, c_type, title, theme, sound_mood, sfx_name = item
        
        # Snap start and end times independently to the transcription segments
        start_seg_idx = find_closest_segment_idx(r_start, segments)
        end_seg_idx = find_closest_segment_idx(r_end, segments)
        
        if end_seg_idx < start_seg_idx:
            end_seg_idx = start_seg_idx
            
        actual_start = segments[start_seg_idx]['start']
        actual_end = segments[end_seg_idx]['end']
        duration = actual_end - actual_start
        
        # Determine transition event (music swell pause between all clips)
        num = idx + 1
        transition_event = "music_swell_pause" if idx < len(rough_blocks) - 1 else "none"
        
        if transition_event != "none":
            # 4.5 seconds music swell pause
            transition_dur = 4.5
            music_file = music_files[idx % len(music_files)] if music_files else "none"
        else:
            transition_dur = 1.0
            music_file = "none"
            
        # Local SFX only, no background music under speech
        audio_layers = []
        if sfx_name != "none":
            audio_layers.append({
                "type": "sound_effect",
                "name": sfx_name,
                "offset": 2.0,
                "duration": min(duration - 3.0, 6.0),
                "volume": 0.12
            })
            
        remix_plan.append({
            "num": num,
            "chron_num": idx + 1,
            "title": title,
            "theme": theme,
            "type": c_type,
            "start": actual_start,
            "end": actual_end,
            "duration": duration,
            "audio_layers": audio_layers,
            "transition": {
                "type": transition_event,
                "duration": transition_dur,
                "music_file": music_file
            }
        })
        
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(remix_plan, f, indent=4)
        
    print(f"Generated clean plan in {plan_file} with {len(remix_plan)} standalone clips.")

if __name__ == "__main__":
    main()
