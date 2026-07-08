import re

# Read transcript dump
with open("scratch/transcript_dump.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Let's search for specific transitions in text
anchors = [
    ("Intro & Kuhn", r"Imagine you've spent 40 years", 0),
    ("Laudan", r"empirical problems and conceptual", 130),
    ("Swales", r"John Swales' CARS model", 160),
    ("Planck Principle", r"Planck's principle", 200),
    ("Copernicus Start", r"Nicholas Copernicus", 230),
    ("Equant", r"The Equant", 280),
    ("Galileo Start", r"leaning tower of Pisa", 370),
    ("Tied Stones Trap", r"Salviati challenges Cenclicio", 420),
    ("Newton Start", r"Renee Descartes", 480),
    ("Kepler conflict", r"Kepler had already", 520),
    ("Lavoisier Start", r"Antoine LaBoisier", 550),
    ("Negative Weight", r"negative weight", 580),
    ("Darwin Start", r"Charles Darwin", 640),
    ("Upland Geese", r"upland geese", 665),
    ("Maxwell Start", r"James Clerk Maxwell", 705),
    ("Capacitor", r"Ampere's law to a charging", 745),
    ("Einstein Start", r"Albert Einstein", 790),
    ("Magnet conductor", r"magnet in one hand", 820),
    ("Photoelectric", r"photoelectric effect", 860),
    ("Quantum packet", r"packets rather than a continuous", 895),
    ("Conclusion start", r"longevity", 950)
]

for name, pattern, start_idx in anchors:
    print(f"\n=================== {name} ===================")
    regex = re.compile(pattern, re.IGNORECASE)
    found = False
    for idx in range(start_idx, min(start_idx + 150, len(lines))):
        if idx >= len(lines):
            break
        if regex.search(lines[idx]):
            found = True
            # Print 5 lines before and 10 lines after
            start_print = max(0, idx - 4)
            end_print = min(len(lines), idx + 10)
            for j in range(start_print, end_print):
                prefix = ">>> " if j == idx else "    "
                print(prefix + lines[j].strip())
            break
    if not found:
        print(f"Pattern '{pattern}' not found near index {start_idx}")
