import re
import json
import html

def parse_docs():
    filepath = r"C:\Users\ashut\.gemini\antigravity\brain\a2c52149-2516-4a3e-9500-2773278c9556\.system_generated\steps\8814\content.md"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Search for all strings matching json pattern
    # Mintlify encodes page data inside script blocks or NextJS self.__next_f.push calls.
    # Let's clean the HTML and extract all readable text.
    clean = re.sub('<[^<]+?>', ' ', content)
    clean = html.unescape(clean)
    
    # Write the cleaned text to a temp file so we can view it
    out_path = "scratch/docs_text.txt"
    with open(out_path, "w", encoding="utf-8") as f_out:
        f_out.write(clean)
        
    print(f"Cleaned text written to {out_path}")
    
    # Search for occurrences of 'finalize_upload' or 'video_id'
    lines = clean.split("\n")
    matches = []
    for idx, line in enumerate(lines):
        if "video_id" in line.lower() or "finalize" in line.lower() or "body" in line.lower() or "param" in line.lower():
            matches.append(f"Line {idx}: {line.strip()[:200]}")
            
    print(f"Found {len(matches)} matching lines. Top 15:")
    for m in matches[:15]:
        print(m)

if __name__ == '__main__':
    parse_docs()
