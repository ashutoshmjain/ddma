import json
import os

def main():
    plan_file = "remix_plan.json"
    if not os.path.exists(plan_file):
        print(f"Error: {plan_file} not found.")
        return
        
    with open(plan_file, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    overlap_count = 0
    
    print("Checking for overlaps at transitions in compiled order:")
    print("--------------------------------------------------")
    
    for idx in range(len(plan) - 1):
        c1 = plan[idx]
        c2 = plan[idx + 1]
        
        # If they are chronologically adjacent in the original audio
        if c1["chron_num"] + 1 == c2["chron_num"]:
            # Check if source times overlap
            if c1["end"] > c2["start"]:
                overlap_count += 1
                diff = c1["end"] - c2["start"]
                print(f"Overlap {overlap_count}: between Seg {c1['num']} ('{c1['title']}', Chron {c1['chron_num']}) and Seg {c2['num']} ('{c2['title']}', Chron {c2['chron_num']})")
                print(f"  Seg {c1['num']} ends at {c1['end']:.2f}s in original")
                print(f"  Seg {c2['num']} starts at {c2['start']:.2f}s in original")
                print(f"  Overlap duration: {diff:.2f} seconds")
                
    if overlap_count == 0:
        print("No source overlaps found between chronologically adjacent segments.")
    else:
        print(f"\nTotal transitions with overlaps: {overlap_count}")

if __name__ == "__main__":
    main()
