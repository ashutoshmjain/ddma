# DeepDive Media Automator (DDMA)

DeepDive Media Automator (DDMA) is a progressive media automation engine powered by **Google Antigravity**. Rather than a simple clip editor, DDMA is an end-to-end production workflow designed to ingest **raw, unedited multi-hour audio recordings**, segment high-engagement topics, overlay background music stings, and compile them into finished, publication-ready media products:

1. **The Long-Form Audio Podcast (Spotify, Apple Podcasts, YouTube Music)**: Compiles all locked segments chronologically, automatically ducking and crossfading background music stings, transitioning raw audio into a fully-produced, high-density podcast episode. For example, [Episode 244 on Spotify](https://open.spotify.com/episode/1KKvm3TbYgxgsffHMj5MwJ?si=NeKNaPJ9QQG11-zcNB92Nw) was progressively curated from a 63-minute raw audio track into a polished, high-value 40-minute master podcast.
2. **The Long-Form Podcast Video (YouTube)**: Automatically joins the segmented video tracks with 5-second curiosity question slide transitions, producing a cohesive, narrative-driven baseline episode video. For example, watch [Episode 244: Architecture of Intellectual Demolition on YouTube](https://youtu.be/9vuNg8t42m8?si=GcVZrzUJ2pN3YZBo) produced entirely using DDMA.
3. **Micro-Promotions (Instagram, TikTok, YouTube Shorts)**: Exports each segment as an individual, high-fidelity vertical video with dynamic title cards and custom Mosaic motion-graphic designs to drive audience acquisition before the main episode launch.

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

---

## 📖 Full Documentation & Interactive Guide

For complete step-by-step guides, advanced CLI reference (`ddma.py`), fast demuxer specifications, and REST API documentation, open the interactive documentation page:
👉 **[DDMA Documentation & Developer Guide](docs/documentation.html)** *(also available directly inside the Curator Dashboard via the **`📖 Docs`** button)*.

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
