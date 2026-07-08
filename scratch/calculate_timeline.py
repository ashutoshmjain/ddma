import json
import os

def main():
    plan_file = "remix_plan.json"
    if not os.path.exists(plan_file):
        print(f"Error: {plan_file} not found.")
        return
        
    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    current_time = 0.0
    
    print("Compiled Audio Timeline Map:")
    print("--------------------------------------------------")
    
    for idx, c in enumerate(plan):
        num = c["num"]
        title = c["title"]
        dur = c["duration"]
        c_type = c["type"]
        chron_num = c["chron_num"]
        
        start_time = current_time
        end_time = current_time + dur
        current_time = end_time
        
        print(f"Segment {num} (Chron {chron_num}) [{c_type}]: '{title}'")
        print(f"  Play time: {start_time:.2f}s -> {end_time:.2f}s ({int(start_time//60)}:{start_time%60:05.2f} -> {int(end_time//60)}:{end_time%60:05.2f})")
        print(f"  Source: {c['start']:.2f}s -> {c['end']:.2f}s")
        
        # Add transition pause or overlap
        trans = c["transition"]
        t_type = trans["type"]
        t_dur = trans["duration"]
        
        if idx < len(plan) - 1:
            if t_type == "crossfade":
                # Crossfade overlaps the two segments by t_dur
                current_time -= t_dur
                print(f"  Transition: Crossfade overlap of {t_dur:.1f}s (New running time offset to {current_time:.2f}s)")
            elif t_type == "music_swell_pause":
                # Music swell adds a vocal pause segment of t_dur, but we do a 0.5s overlap on both ends
                pause_len = t_dur - 1.0 # net duration added (since we do 0.5s crossfade on both sides)
                # Wait, in the code:
                # step1: combined_running acrossfade transition (0.5s) -> duration = len(combined_running) + len(transition) - 0.5
                # step2: step1 acrossfade current (0.5s) -> duration = len(step1) + len(current) - 0.5
                # Total len = len(combined_running) + len(transition) - 0.5 + len(current) - 0.5
                # Net length added by transition = len(transition) - 1.0
                current_time += pause_len
                print(f"  Transition: Music Swell Pause net addition of {pause_len:.2f}s (New running time: {current_time:.2f}s)")
            elif t_type == "rewind_correction":
                # Rewind adds a segment of t_dur, but we do a 0.2s crossfade on both ends
                pause_len = t_dur - 0.4 # net duration added
                current_time += pause_len
                print(f"  Transition: Rewind Correction net addition of {pause_len:.2f}s (New running time: {current_time:.2f}s)")
            else:
                print(f"  Transition: Unknown transition type {t_type}")
                
if __name__ == "__main__":
    main()
