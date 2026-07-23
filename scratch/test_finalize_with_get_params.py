import requests
import json
import os

def test_flow():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        
    api_key = settings.get("mosaic_api_key")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    video_file = "clips/244-1.mp4"
    file_size = os.path.getsize(video_file)
    filename = os.path.basename(video_file)
    
    # 1. get_upload_url WITH body metadata
    print("Step 1: Requesting upload URL with file metadata...")
    payload = {
        "filename": filename,
        "content_type": "video/mp4",
        "size": file_size
    }
    res = requests.post(
        f"{base_url}/uploads/video/get_upload_url", 
        headers=headers, 
        json=payload
    )
    if res.status_code != 200:
        print(f"Failed get_upload_url: {res.text}")
        return
        
    data = res.json()
    video_id = data.get("video_id")
    upload_url = data.get("upload_url")
    upload_fields = data.get("upload_fields", {})
    
    print(f"video_id: {video_id}")
    
    # 2. Upload to GCS
    print(f"Step 2: Uploading {video_file} ({file_size} bytes) to GCS...")
    with open(video_file, "rb") as f:
        files = {"file": (filename, f, "video/mp4")}
        res_gcs = requests.post(upload_url, data=upload_fields, files=files)
    print(f"GCS code: {res_gcs.status_code}")
    
    # 3. Finalize upload
    print("Step 3: Finalizing upload...")
    res_finalize = requests.post(
        f"{base_url}/uploads/video/finalize_upload",
        headers=headers,
        json={"video_id": video_id}
    )
    print(f"Finalize code: {res_finalize.status_code}")
    print(f"Finalize body: {res_finalize.text}")

if __name__ == '__main__':
    test_flow()
