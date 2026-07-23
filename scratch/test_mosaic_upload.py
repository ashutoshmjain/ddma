import requests
import json
import os

def test_upload():
    # Load settings
    with open('settings.json', 'r') as f:
        settings = json.load(f)
    
    api_key = settings.get("mosaic_api_key")
    if not api_key:
        print("Error: No mosaic_api_key in settings.json")
        return
    
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    print("Step 1: Requesting upload URL...")
    res = requests.post(f"{base_url}/uploads/video/get_upload_url", headers=headers)
    print(f"Response status: {res.status_code}")
    print(f"Response body: {res.text}")
    
    if res.status_code != 200:
        return
    
    upload_data = res.json()
    upload_url = upload_data.get("upload_url")
    upload_fields = upload_data.get("upload_fields", {})
    video_id = upload_data.get("video_id")
    
    # Create a tiny mock MP4 file (or use an existing one)
    # Let's use the first 100KB of clips/244-15.mp4 if it exists, or create a mock file
    mock_file = "clips/244-1.mp4"
    if not os.path.exists(mock_file):
        print(f"Error: {mock_file} does not exist.")
        return
            
    print(f"\nStep 2: Uploading real valid file to GCS: {upload_url}")
    with open(mock_file, "rb") as f:
        files = {
            "file": (os.path.basename(mock_file), f, "video/mp4")
        }
        # S3 requires the data fields to be sent BEFORE the file
        res_s3 = requests.post(upload_url, data=upload_fields, files=files)
        
    print(f"S3 response code: {res_s3.status_code}")
    print(f"S3 response body: {res_s3.text[:1000]}")
    
    print("\nStep 3: Finalizing upload on Mosaic...")
    res_finalize = requests.post(
        f"{base_url}/uploads/video/finalize_upload",
        headers=headers,
        json={"video_id": video_id}
    )
    print(f"Finalize response code: {res_finalize.status_code}")
    print(f"Finalize response body: {res_finalize.text}")

if __name__ == '__main__':
    test_upload()
