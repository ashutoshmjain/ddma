import requests
import json
import sys
import os
import subprocess

def download_and_compile(clip_num, run_id):
    project_id = "episode_244"
    print(f"Bypassing API upload. Fetching manually rendered video for Clip {clip_num} using Run ID: {run_id}...")
    
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        
    api_key = settings.get("mosaic_api_key")
    if not api_key:
        print("Error: No mosaic_api_key in settings.json")
        return
        
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    # Query run details
    run_detail_url = f"{base_url}/agent_run/{run_id}"
    res = requests.get(run_detail_url, headers=headers)
    if res.status_code != 200:
        print(f"Error: Failed to fetch run details for {run_id}. Response: {res.text}")
        return
        
    run_info = res.json()
    status = run_info.get("status")
    print(f"Run status: {status}")
    
    if status != "completed":
        print(f"Error: Run {run_id} is not completed (status is '{status}'). Can only download completed runs.")
        return
        
    outputs = run_info.get("outputs", [])
    if not outputs or not outputs[0].get("video_url"):
        print("Error: Completed run returned no output video URL.")
        return
        
    final_video_url = outputs[0]["video_url"]
    file_path = os.path.join("clips", f"244-{clip_num}.mp4")
    backup_path = os.path.join("clips", f"244-{clip_num}-original.mp4")
    
    # Clear existing draft files
    for p in [file_path, backup_path]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                print(f"Warning: Could not remove old file {p}: {e}")
                
    print(f"Downloading completed render from: {final_video_url}")
    res_download = requests.get(final_video_url, stream=True)
    if res_download.status_code != 200:
        print(f"Error downloading video: {res_download.status_code}")
        return
        
    os.makedirs("clips", exist_ok=True)
    with open(file_path, "wb") as f_out:
        for chunk in res_download.iter_content(chunk_size=8192):
            f_out.write(chunk)
            
    print(f"Successfully downloaded raw Mosaic video to {file_path}")
    
    # Save the run_id in plan.json under projects/episode_244/plan.json
    plan_path = "projects/episode_244/plan.json"
    if os.path.exists(plan_path):
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                plan = json.load(f)
            for c in plan:
                if int(c.get("num", -1)) == int(clip_num):
                    c["mosaic_run_id"] = run_id
                    break
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=4)
            print(f"Saved mosaic_run_id {run_id} in {plan_path}")
        except Exception as e:
            print(f"Warning: Failed to save run ID to plan.json: {e}")
            
    # Compile the clip to prepend the intro title card
    print("Compiling clip to add intro card...")
    cmd_compile = [
        sys.executable, "ddma.py", "compile-clip",
        "--num", str(clip_num),
        "--plan-file", plan_path
    ]
    comp_res = subprocess.run(cmd_compile, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if comp_res.returncode != 0:
        print(f"Error: compilation failed: {comp_res.stderr.decode('utf-8')}")
        return
        
    print(f"SUCCESS: Clip {clip_num} has been successfully downloaded and compiled with infographics!")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python scratch/download_manual_run.py <clip_num> <run_id>")
    else:
        download_and_compile(sys.argv[1], sys.argv[2])
