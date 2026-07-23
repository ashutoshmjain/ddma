import requests
import json
import os

def test_queries():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        
    api_key = settings.get("mosaic_api_key")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    # Get whoami to get org/workspace details
    whoami = requests.get(f"{base_url}/whoami", headers=headers).json()
    org_id = whoami.get("organization_id")
    
    print("Getting upload URL...")
    res = requests.post(f"{base_url}/uploads/video/get_upload_url", headers=headers)
    data = res.json()
    video_id = data.get("video_id")
    upload_url = data.get("upload_url")
    upload_fields = data.get("upload_fields", {})
    
    print(f"video_id: {video_id}, org_id: {org_id}")
    
    # Upload to GCS
    video_file = "clips/244-1.mp4"
    with open(video_file, "rb") as f:
        files = {"file": (os.path.basename(video_file), f, "video/mp4")}
        requests.post(upload_url, data=upload_fields, files=files)
        
    # Try different combinations of query params and JSON bodies
    test_cases = [
        # Query params
        (f"{base_url}/uploads/video/finalize_upload", {"video_id": video_id}),
        (f"{base_url}/uploads/video/finalize_upload?organization_id={org_id}", {"video_id": video_id}),
        (f"{base_url}/uploads/video/finalize_upload?workspace_id={org_id}", {"video_id": video_id}),
        # JSON body additions
        (f"{base_url}/uploads/video/finalize_upload", {"video_id": video_id, "organization_id": org_id}),
        (f"{base_url}/uploads/video/finalize_upload", {"video_id": video_id, "workspace_id": org_id}),
    ]
    
    for idx, (url, payload) in enumerate(test_cases):
        print(f"\nTest {idx+1}: POST to {url} with {payload}")
        res_fin = requests.post(url, headers=headers, json=payload)
        print(f"Code: {res_fin.status_code}")
        print(f"Body: {res_fin.text}")
        if res_fin.status_code == 200:
            print("SUCCESS!")
            break

if __name__ == '__main__':
    test_queries()
