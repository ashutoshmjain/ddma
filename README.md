# DeepDive Media Automator (DDMA)

DeepDive Media Automator (DDMA) is a progressive media automation engine powered by **Google Antigravity**. Rather than a simple clip editor, DDMA is an end-to-end production workflow designed to ingest **raw, unedited multi-hour audio recordings**, segment high-engagement topics, overlay background music stings, and compile them into finished, publication-ready media products:

1. **The Long-Form Audio Podcast (Spotify, Apple Podcasts, YouTube Music)**: Compiles all locked segments chronologically, automatically ducking and crossfading background music stings, transitioning raw audio into a fully-produced, high-density podcast episode. For example, [Episode 244 on Spotify](https://open.spotify.com/episode/1KKvm3TbYgxgsffHMj5MwJ?si=NeKNaPJ9QQG11-zcNB92Nw) was progressively curated from a 63-minute raw audio track into a polished, high-value 40-minute master podcast.
2. **The Long-Form Podcast Video (YouTube)**: Automatically joins the segmented video tracks with 5-second curiosity question slide transitions, producing a cohesive, narrative-driven baseline episode video. For example, watch [Episode 244: Architecture of Intellectual Demolition on YouTube](https://youtu.be/9vuNg8t42m8?si=GcVZrzUJ2pN3YZBo) produced entirely using DDMA.
3. **Micro-Promotions (Instagram, TikTok, YouTube Shorts)**: Exports each segment as an individual, high-fidelity vertical video with dynamic title cards and custom Mosaic motion-graphic designs to drive audience acquisition before the main episode launch.

---

## ⚡ Setup & Quickstart Guide

Choose the path that fits your workflow:
* **🚀 Track A: The Easy Way (Google Antigravity on Windows)** — 100% automated setup with natural language. No manual terminal steps or virtual environment creation needed!
* **🐧 Track B: The Manual Way (Isolated Native WSL Linux on Windows)** — Complete step-by-step instructions for native Linux isolation. Written for absolute beginners.

---

### 🚀 Track A: The Easy Way (Google Antigravity on Windows)

Let **Google Antigravity** handle environment provisioning, dependency installation, FFmpeg verification, transcription, and server launch automatically!

#### 1. Install Google Antigravity
Install the Antigravity CLI globally (or open the Antigravity IDE / Desktop Assistant):
```bash
npm install -g @google/antigravity-cli
```

#### 2. Prompt Antigravity
Open Antigravity in your terminal or IDE and give it this natural language instruction:
> **"Clone `https://github.com/ashutoshmjain/ddma.git`, install all Python dependencies from `requirements.txt`, verify FFmpeg is installed, start the local curator server (`python scratch/run_curator.py`), and transcribe my audio file."**

#### 🧠 How Antigravity Handles Setup Automatically:
* **Repository & Dependencies**: Clones `ddma.git` and inspects `requirements.txt` to install `openai-whisper`, `torch`, `requests`, `typer`, `pillow`, and `pyyaml`.
* **System Tools**: Automatically verifies or installs system binaries (`ffmpeg`) via `winget`, `brew`, or `apt`.
* **Server Execution**: Launches the Curator web server automatically and provides the local web URL (`http://localhost:8000/curator.html?project=episode_245`).

---

### 🐧 Track B: The Manual Way (Isolated Native WSL Linux on Windows)

If you prefer to run inside **WSL (Windows Subsystem for Linux)** with native Linux execution and total environment isolation from Windows, follow this beginner-friendly step-by-step guide.

> 💡 **What is WSL?** WSL allows you to run a native Linux terminal inside Windows.
> 💡 **What is `localhost`?** `localhost` means your own computer. When Curator runs on `http://localhost:8000`, it means your computer is serving the web interface locally on port `8000`.
> 💡 **What is a `.venv` (Virtual Environment)?** A virtual environment is an isolated "folder box" for Python packages so they don't interfere with your system or other projects.

---

#### 📌 Step 1: Open Your WSL Linux Terminal
If you haven't installed WSL yet, open Windows PowerShell as Administrator and run:
```powershell
wsl --install
```
Once installed, open **WSL** (or Ubuntu) from your Windows Start Menu.

---

#### 📌 Step 2: Navigate to Your DDMA Directory
In your WSL terminal, navigate to your DDMA project folder. 

* **If working directly inside your existing Windows project folder:**
  *(Windows drive `C:` is mounted inside WSL under `/mnt/c/`)*
  ```bash
  cd /mnt/c/Users/ashut/OneDrive/Desktop/github/deepDive/ddma
  ```
* **Or if cloning a fresh isolated copy inside WSL native home directory:**
  ```bash
  cd ~
  git clone https://github.com/ashutoshmjain/ddma.git
  cd ~/ddma
  ```

---

#### 📌 Step 3: Install Linux System Dependencies (Run Once)
Install system packages (`python3-full`, `python3-venv`, `python3-pip`, and `ffmpeg`) inside Linux:
```bash
sudo apt update && sudo apt install -y python3-full python3-venv python3.14-venv python3-pip ffmpeg
```
* **`sudo`**: Runs the installer with administrative privileges inside Linux.
* **`apt`**: The standard Linux package manager.
* **`ffmpeg`**: The multimedia processing library used for video stream remuxing and title card concatenation.
* **`python3-full` / `python3-venv`**: Provides Python's virtual environment creation tools.

---

#### 📌 Step 4: Create and Activate Your Isolated Virtual Environment (`.venv`)
Inside your DDMA directory, create a clean virtual environment folder named `.venv`:

```bash
# 1. Remove any broken draft environments (if retrying)
rm -rf .venv

# 2. Create a clean Linux virtual environment
python3 -m venv .venv

# 3. Activate the environment
source .venv/bin/activate
```
*(When active, your terminal prompt will show `(.venv)` at the beginning of the line!)*

---

#### 📌 Step 5: Install Python Dependencies
With `(.venv)` active, install all required Python libraries from `requirements.txt`:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
This installs:
* **`openai-whisper`** (AI speech-to-text transcription engine)
* **`requests`** (Mosaic API status polling & video downloader)
* **`typer`** (CLI automation framework)
* **`pillow`** (Dynamic Intro Title Card & Outro Curiosity Card PNG image renderer)
* **`google-generativeai`** (Gemini AI Clip Remixing engine)

---

#### 📌 Step 6: Launch the Curator Server
Start the local Curator web server:
```bash
python scratch/run_curator.py
```

You will see the server startup log:
```text
Serving on http://localhost:8000
```

Open your web browser (Chrome, Edge, Firefox) and navigate to:
👉 **[http://localhost:8000/curator.html?project=episode_245](http://localhost:8000/curator.html?project=episode_245)**

---

#### 🔄 How to Resume Curator Next Time (Future Daily Usage)
Whenever you open your WSL terminal in the future, you only need to run these 3 quick commands:

```bash
cd /mnt/c/Users/ashut/OneDrive/Desktop/github/deepDive/ddma
source .venv/bin/activate
python scratch/run_curator.py
```

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
