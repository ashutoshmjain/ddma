import requests
import json
import os
import time

def test_delay():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        
    api_key = settings.get("mosaic_api_key")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    print("Step 1: Getting upload URL...")
    res = requests.post(f"{base_url}/uploads/video/get_upload_url", headers=headers)
    data = res.json()
    video_id = data.get("video_id")
    upload_url = data.get("upload_url")
    upload_fields = data.get("upload_fields", {})
    
    print(f"video_id: {video_id}")
    
    # Upload to GCS
    video_file = "clips/244-1.mp4"
    print(f"Uploading {video_file} to GCS...")
    with open(video_file, "rb") as f:
        files = {"file": (os.path.basename(video_file), f, "video/mp4")}
        res_gcs = requests.post(upload_url, data=upload_fields, files=files)
    print(f"GCS code: {res_gcs.status_code}")
    
    # Try different delays
    for delay in [5, 15, 30]:
        print(f"\nWaiting {delay} seconds before finalizing...")
        time.sleep(delay)
        res_finalize = requests.post(
            f"{base_url}/uploads/video/finalize_upload",
            headers=headers,
            json={"video_id": video_id}
        )
        print(f"Finalize response code: {res_finalize.status_code}")
        print(f"Finalize response body: {res_finalize.text}")
        if res_finalize.status_code == 200:
            print("SUCCESS!")
            break

if __name__ == '__main__':
    test_delay()
