import requests
import json
import os
import subprocess

def test_curl_flow():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        
    api_key = settings.get("mosaic_api_key")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    print("Step 1: Requesting upload URL...")
    res = requests.post(f"{base_url}/uploads/video/get_upload_url", headers=headers)
    if res.status_code != 200:
        print(f"Failed get_upload_url: {res.text}")
        return
        
    data = res.json()
    video_id = data.get("video_id")
    upload_url = data.get("upload_url")
    upload_fields = data.get("upload_fields", {})
    
    print(f"video_id: {video_id}")
    video_file = "clips/244-1.mp4"
    
    # Construct curl command
    # GCS requires form fields to be in order, with 'file' at the very end
    curl_args = ["curl", "-v", "-X", "POST"]
    for k, v in upload_fields.items():
        curl_args.extend(["-F", f"{k}={v}"])
    curl_args.extend(["-F", f"file=@{video_file}"])
    curl_args.append(upload_url)
    
    print(f"\nStep 2: Uploading {video_file} via curl to GCS...")
    proc = subprocess.run(curl_args, capture_output=True, text=True)
    print(f"curl exit code: {proc.returncode}")
    print(f"curl stderr (truncated):\n{proc.stderr[-1000:]}")
    print(f"curl stdout: {proc.stdout}")
    
    print("\nStep 3: Finalizing upload on Mosaic...")
    res_finalize = requests.post(
        f"{base_url}/uploads/video/finalize_upload",
        headers=headers,
        json={"video_id": video_id}
    )
    print(f"Finalize response code: {res_finalize.status_code}")
    print(f"Finalize response body: {res_finalize.text}")

if __name__ == '__main__':
    test_curl_flow()
