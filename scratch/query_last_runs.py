import requests
import json

def get_runs():
    with open('settings.json', 'r') as f:
        settings = json.load(f)
        
    api_key = settings.get("mosaic_api_key")
    agent_id = settings.get("mosaic_agent_id")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = "https://api.mosaic.so"
    
    # Query runs of this agent
    url = f"{base_url}/agent/{agent_id}/runs"
    print(f"Fetching runs from: {url}")
    res = requests.get(url, headers=headers)
    print(f"Response code: {res.status_code}")
    if res.status_code != 200:
        print(f"Error body: {res.text}")
        return
        
    runs = res.json()
    # The API might return a list or a dict. Let's inspect it.
    if isinstance(runs, dict):
        # Print keys
        print(f"Keys in response: {list(runs.keys())}")
        # Try to find list under a key
        for k, v in runs.items():
            if isinstance(v, list):
                runs = v
                break
                
    if not isinstance(runs, list):
        print(f"Unexpected response structure: {runs}")
        return
        
    print(f"Found {len(runs)} runs. Inspecting the 3 most recent runs:")
    for idx, run in enumerate(runs[:3]):
        run_id = run.get("id")
        status = run.get("status")
        created_at = run.get("created_at")
        print(f"\n--- Run {idx+1} ---")
        print(f"Run ID: {run_id}")
        print(f"Status: {status}")
        print(f"Created At: {created_at}")
        
        # Query individual run details
        run_detail_url = f"{base_url}/agent_run/{run_id}"
        detail_res = requests.get(run_detail_url, headers=headers)
        if detail_res.status_code == 200:
            detail = detail_res.json()
            print(f"Outputs: {json.dumps(detail.get('outputs'), indent=2)}")
            # Print input parameters if present
            inputs = detail.get("inputs") or detail.get("parameters")
            if inputs:
                print(f"Inputs: {json.dumps(inputs, indent=2)[:500]}...")
        else:
            print(f"Failed to fetch detail: {detail_res.status_code} - {detail_res.text}")

if __name__ == '__main__':
    get_runs()
