import requests
import json
import os

def test_finalize_variants():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        
    api_key = settings.get("mosaic_api_key")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    print("Step 1: Getting upload URL...")
    res = requests.post(f"{base_url}/uploads/video/get_upload_url", headers=headers)
    if res.status_code != 200:
        print(f"Failed get_upload_url: {res.text}")
        return
        
    data = res.json()
    video_id = data.get("video_id")
    upload_url = data.get("upload_url")
    upload_fields = data.get("upload_fields", {})
    key = upload_fields.get("key")
    
    print(f"video_id: {video_id}")
    print(f"key: {key}")
    
    # Upload the valid file first so that GCS has it
    video_file = "clips/244-1.mp4"
    print(f"Uploading {video_file} to GCS...")
    with open(video_file, "rb") as f:
        files = {"file": (os.path.basename(video_file), f, "video/mp4")}
        res_s3 = requests.post(upload_url, data=upload_fields, files=files)
    print(f"GCS upload code: {res_s3.status_code}")
    
    # Try different finalize payloads
    payloads = [
        {"video_id": video_id},
        {"id": video_id},
        {"video_id": video_id, "key": key},
        {"id": video_id, "key": key},
        {"video_id": video_id, "upload_key": key},
        {"video_id": video_id, "filename": os.path.basename(video_file)},
    ]
    
    for i, payload in enumerate(payloads):
        print(f"\nVariant {i+1}: Trying payload {payload}")
        res_finalize = requests.post(
            f"{base_url}/uploads/video/finalize_upload",
            headers=headers,
            json=payload
        )
        print(f"Response code: {res_finalize.status_code}")
        print(f"Response body: {res_finalize.text}")
        if res_finalize.status_code == 200:
            print("SUCCESS!")
            break

if __name__ == '__main__':
    test_finalize_variants()
