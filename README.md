# DeepDive Media Automator (DDMA)

DeepDive Media Automator (DDMA) is an automated podcast clip curation toolkit and web dashboard powered by **Google Antigravity**. It transcribes long podcast episodes, curates high-engagement clips with sample-accurate word boundaries, mixes sound/music stings, and compiles ready-to-publish video assets for TikTok, Instagram Reels, and YouTube Shorts.

---

## 🤖 Recommended Quickstart with Google Antigravity (AGY)

Skip manual repository setup, virtual environments, and manual FFmpeg/Whisper installations! You can let **Google Antigravity** handle the entire setup, environment provisioning, transcription, and clip rendering automatically.

### 1. Install Google Antigravity
Install the Antigravity CLI globally (or open the Antigravity IDE / Desktop Assistant):
```bash
npm install -g @google/antigravity-cli
```

### 2. Prompt Antigravity
Open Antigravity in your terminal or IDE and give it this natural language instruction:
> **"Clone `https://github.com/ashutoshmjain/ddma.git`, install all Python dependencies from `requirements.txt`, verify FFmpeg is installed, start the local curator server (`python scratch/run_curator.py`), and transcribe my audio file."**

### 🧠 How Antigravity Knows What to Do:
- **Repository Source**: Antigravity uses the target URL (`https://github.com/ashutoshmjain/ddma.git`) to clone the codebase.
- **Dependencies**: It inspects `requirements.txt` to install `openai-whisper`, `fastapi`, `pillow`, `typer`, and checks for `ffmpeg` (installing it via `winget`, `brew`, or `apt` if missing).
- **Execution Blueprint**: Once inside the codebase, Antigravity automatically reads [`.agents/AGENTS.md`](file:///.agents/AGENTS.md) and [README.md](file:///README.md) to discover exact server commands, API specs, and execution workflows.

---

## 📋 Antigravity Agent Instruction Sheet (`AGENTS.md`)

When executing media automation tasks, Antigravity follows the built-in operational instructions in [`.agents/AGENTS.md`](file:///.agents/AGENTS.md):

### 🔄 The Automated Pipeline

1. **Transcribe**:
   ```bash
   python ddma.py transcribe --audio <episode>.mp3
   ```
   Transcribes the long audio file using OpenAI Whisper with native word-level timestamps (`word_timestamps=True`).

2. **Plan & Curate**:
   ```bash
   python ddma.py plan --audio <episode>.mp3 --ranges '<start>-<end>'
   ```
   Curates high-engagement concepts, sets snapped segment boundaries, title formatting, and curiosity question transitions (`plan.json`).

3. **Audio Slice**:
   ```bash
   python ddma.py cut --audio <episode>.mp3 --plan-file plan.json --out-dir clips
   ```
   Splits long audio into sample-accurate MP3 clip slices, stripping leading disfluencies and tight trailing silence.

4. **Draft Mux**:
   ```bash
   python ddma.py mux-clip --num <clip_number>
   ```
   Merges audio slices with dynamically generated black background canvas videos (`740x740`) for Mosaic draft renders.

5. **Infographic Overlay (Mosaic AI)**:
   Sends the draft video to the Mosaic API to generate motion graphics and visual infographics.

6. **Add Intro Title Cards & Crossfades**:
   ```bash
   python ddma.py compile-clip --num <clip_number>
   ```
   Equalizes stream durations, generates charcoal title card intros with Part 1 exception rules, and concatenates losslessly.

7. **Combine Full Episode Video / Audio**:
   ```bash
   python scratch/combine_clips_demuxer.py
   ```
   Stitches all locked clips and 5.0s curiosity question bridge transition slides into a single `combined_<episode>.mp4` published video in seconds.

---

## 🌌 Key Features & Capabilities

* **Multi-Project Management**: Curate multiple episodes side-by-side with local audio files, word-level Whisper transcripts, and clip plans in project-specific workspaces.
* **Collapsible & Resizable IDE-style Layout**: Drag dividers to adjust transcription/clips real estate. Collapse the sidebar to maximize focus.
* **Word-Level Curation & Timeline Snapping**: Double-click or select transcript words to set precise sub-second boundaries. Highlights used ranges to prevent overlapping selections.
* **Per-Segment Music Volume Mixer**: Mix background music stings. Set individual duration, crossfade transition, and custom volume level multipliers (e.g. `0.20` for subtle background ducking).
* **Global Sting Manager**: Upload new music stings directly through the settings panel to make them globally available.
* **Theme Customization**: Switch between **Nordic Breeze (Light)**, **Cyberpunk (Neon Cyan/Purple)**, and **Midnight (Dark default)**.
* **Dynamic Exporters & Instant Demuxing**:
  * **Audio (`.mp3`)**: Compiles mixed segments directly.
  * **Fast Video Demuxer (`.mp4`)**: Lossless `-c copy` stream stitching concatenates 40-minute episode files in 2–4 seconds!
* **Automatic Title Card Intro Prepending**: Pillow generates clean title cards with multi-line wrapping and joins them to the master clip using FFmpeg timescale normalization.
* **Mosaic AI Ingest & Recovery Integration**:
  * **Automated Upload & Execution**: Export local draft video compiles directly to the Mosaic API for AI motion graphics overlays.
  * **Self-Healing Recovery & Cache**: Automatically resumes background polling/download threads across server restarts and browser reloads.
* **🔄 Granular AI Remixing & In-Context Recasting**:
  * Click `🔄 Remix` on any clip to recast it using Gemini (analyzing preceding locked clips for style, pacing, and curiosity questions).
* **🎬 Editor's Preview Player & E2E Testing**:
  * **Consolidated Single-Player Engine**: Plays all selected clips sequentially with WebAudio/HTML5 volume synchronization.
  * **Automated E2E Test Suite**: Headless Puppeteer test scripts (`scratch/test-env/test_curator.js` & `scratch/test-env/test_player.js`) ensure 100% regression-free updates.
