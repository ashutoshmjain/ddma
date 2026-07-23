import os
import json
import subprocess
import sys

plan_path = os.path.join("projects", "episode_244", "plan.json")
if not os.path.exists(plan_path):
    print(f"Error: {plan_path} not found")
    sys.exit(1)

with open(plan_path, "r", encoding="utf-8") as f:
    clips = json.load(f)

print(f"Loaded {len(clips)} clips from plan.json.")

python_exe = sys.executable

results = []

for clip in clips:
    num = clip["num"]
    title = clip.get("title", "")
    locked = clip.get("locked", False)
    
    print(f"\n--- Processing Clip {num} (Locked: {locked}, Title: '{title}') ---")
    
    # Run compile-clip
    cmd = [
        python_exe, "ddma.py", "compile-clip",
        "--num", str(num),
        "--plan-file", plan_path
    ]
    
    comp_res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if comp_res.returncode == 0:
        print(f"[OK] Clip {num} successfully compiled!")
        results.append({
            "num": num,
            "title": title,
            "status": "success",
            "top_line": f"EPISODE 244" if num == 1 else f"EPISODE 244 • PART {num}",
            "bottom_line": "Scientific Paradigm Shift Strategies" if num == 1 else title
        })
    else:
        print(f"[FAILED] Clip {num} compilation failed: {comp_res.stderr or comp_res.stdout}")
        results.append({
            "num": num,
            "title": title,
            "status": "failed",
            "error": comp_res.stderr or comp_res.stdout
        })

print("\n================ SUMMARY ================")
for r in results:
    if r["status"] == "success":
        print(f"Clip {r['num']:2d} | Top: '{r['top_line']}' | Bottom: '{r['bottom_line']}' | [OK]")
    else:
        print(f"Clip {r['num']:2d} | [FAILED]: {r.get('error')}")
