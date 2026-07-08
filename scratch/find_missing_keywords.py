import re

with open("scratch/transcript_dump.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

search_words = ["LaBoisier", "flogiston", "geese", "Planck", "longev", "senesc", "block"]

for sw in search_words:
    print(f"\nMatches for: {sw}")
    regex = re.compile(sw, re.IGNORECASE)
    count = 0
    for idx, line in enumerate(lines):
        if regex.search(line):
            print(f"  Line {idx}: {line.strip()}")
            count += 1
            if count >= 10:
                print("  ... truncated matches")
                break
