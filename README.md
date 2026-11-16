# DeepDive Media Automator (DDMA)

DeepDive Media Automator (DDMA) is a progressive media automation engine powered by **Google Antigravity**.

---

## 💡 The DDMA Philosophy: A Ground-Up Inversion of Media Production

Typically, when creating a podcast, video, or movie, creators follow a **top-down paradigm**:
1. Record hours of raw audio and video.
2. Spend days editing a master long-form podcast or film first.
3. Slice out short trailers or highlights after the fact for social media platforms like TikTok, Instagram Reels, or YouTube Shorts.

**DDMA takes a fundamentally different, ground-up approach—a total inversion of traditional media workflows.**

Rather than slicing down a monolithic master recording, DDMA builds media **bottom-up from first-principles micro-chunks**:
1. **Intelligent Short-Form First**: DDMA ingests raw audio, transcribes it at the word level, and intelligently splits it into autonomous, high-density **~2-minute short clips** optimized specifically for social media engagement.
2. **Emergent Long-Form Outcomes**: When each standalone short clip is perfected (with dynamic title cards, background music ducking, and motion graphics), the long-form audio podcast (Spotify/Apple) and long-form infographic video (YouTube) **emerge naturally as downstream outcomes** by compiling these micro-clips.

> 🎯 **If every 2-minute short is great, the resulting long-form podcast or video is guaranteed to be a filler-free master artifact.**

---

## ⚙️ Creative Automation vs. Social Media Scheduling

> [!NOTE]
> **What "Automation" Means in DDMA**:
> Automation in DDMA does **NOT** mean auto-posting videos directly to TikTok or fetching analytics from Instagram.
> Instead, **DDMA automates the creative production process itself**—intelligent topic segmentation, sub-second word-level snapping, automated audio ducking and crossfading, motion-graphics rendering, and seamless bottom-up long-form video demuxing.

---

## 🧩 Architecture: The 3 Schematic Modules

DDMA is architected around three primary schematic modules:

```mermaid
graph LR
    A["🎙️ Transcription Protocol<br/>(Whisper Word-Level Alignment & Topic Discovery)"] --> B["⚡ Clip Dynamics<br/>(2-min Standalone Social Shorts, Title Cards & Ducking)"]
    B --> C["🎧 Long-Form Emergence<br/>(Spotify Podcast MP3 & YouTube Infographic MP4)"]
```

1. **🎙️ Transcription Protocol**:
   Processes raw unedited audio using local Whisper speech-to-text models for word-level timestamped transcription, aligning transcript words and discovering natural high-engagement topic boundaries.

2. **⚡ Clip Dynamics**:
   Focuses on crafting perfected, standalone ~2-minute short clips. Includes dynamic intro title card image generation (Pillow), background music sting ducking and quarter-sine crossfading, and AI motion-graphic rendering (Mosaic).

3. **🎧 Long-Form Emergence**:
   Synthesizes the individual micro-clips chronologically into master, publication-ready outcomes:
   * **Master Audio Podcast (`.mp3`)**: Seamlessly crossfaded audio episodes for Spotify, Apple Podcasts, and YouTube Music (e.g. [Episode 244 on Spotify](https://open.spotify.com/episode/1KKvm3TbYgxgsffHMj5MwJ?si=NeKNaPJ9QQG11-zcNB92Nw)).
   * **Master Infographic Video (`.mp4`)**: Cohesive YouTube video episodes joined with 5-second curiosity question slide transitions (e.g. [Episode 244 on YouTube](https://youtu.be/9vuNg8t42m8?si=GcVZrzUJ2pN3YZBo)).

---

> [!IMPORTANT]
> 💻 **Minimum Hardware Specifications & System Requirements**:
> Because DDMA performs local AI speech-to-text transcription (Whisper), high-definition video stream remuxing (FFmpeg), and dynamic image overlays (Pillow), we recommend the following minimum hardware configuration:
> * **CPU**: Quad-Core Processor (Intel Core i5 8th Gen+ / AMD Ryzen 5 3000+ or Apple Silicon M1/M2/M3).
> * **RAM**: **8 GB Minimum** (16 GB Recommended for handling multi-hour audio files, Whisper model weights, and 1080p/740p video rendering smoothly).
> * **Disk Storage**: **10 GB Free Disk Space** (for Python libraries, PyTorch weights, FFmpeg binaries, and temporary media clip buffers).
> * **GPU (Optional)**: NVIDIA GPU with CUDA support for accelerated transcription (automatically falls back to CPU if no GPU is available).
> * **Supported Operating Systems**: Windows 10/11 (with WSL2), macOS 12+, or Ubuntu Linux 20.04+.

---


## 🗄️ Setting up dd_hub (the workspace)

dd_hub is the workspace — a Google Drive folder that holds the plan, settings, inputs, working assets, and audio/video outputs. DDMA reads from and writes to dd_hub. GitHub is only the intermediary for the *published* Active Master clips; dd_hub is the live workspace.

> [!IMPORTANT]
> **The core rule**: The code only does **local file I/O against a local path**. It **never** calls the Google Drive web API for file access. So dd_hub must be mounted as a local filesystem path on every machine that runs DDMA. The code reads the mount path from the `DD_HUB_ROOT` environment variable.

### What you need

* A Google Drive folder to be your dd_hub. Create a new folder, or use an existing one. Note its folder ID from the Drive URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`.
* The folder should contain (create any that are missing): `episodes/`, `vault/`, `inputs/`, `audio/`, `video/`, `mosaics/`, `manims/`, `rules/`.

### Windows (the reference environment)

* Install Google Drive for Desktop. It mounts your Drive as a local drive (typically `G:\My Drive\`).
* Your dd_hub folder is then at `G:\My Drive\dd_hub` (if your folder is named dd_hub).
* Set `DD_HUB_ROOT` to that path. The code's first candidate is `G:\My Drive\dd_hub`, so this works out of the box.
* All reads/writes are plain local file I/O through the mount. No Drive web API calls are made.

### Linux / VM / Docker

* Install rclone. Configure a Google Drive remote (for example, named `gdrive`).
* Mount the dd_hub folder by its ID to a local path (for example `/mnt/gdrive/dd_hub`):
  ```bash
  rclone mount gdrive: /mnt/gdrive/dd_hub --drive-root-folder-id <FOLDER_ID> --vfs-cache-mode full --daemon
  ```
* Use `--vfs-cache-mode full` — the pipeline does many small reads/writes, and the cache makes it fast. A generous `--vfs-cache-max-size` helps.
* Set `DD_HUB_ROOT` to the mount path (for example `/mnt/gdrive/dd_hub`) and persist it (shell profile, systemd unit, or Docker entrypoint) so it survives new shells.
* In Docker, the entrypoint mounts the Drive folder by ID via rclone to a local path, sets `DD_HUB_ROOT`, then starts the server.

### Settings (the vault)

* The canonical settings file is `dd_hub/vault/settings.json`. It holds the app settings **and** the API keys (Mosaic, Gemini, etc.).
* Create it from `settings.template.json` (in the repo root) and fill in your keys.
* `settings.json` is **never** committed to git. The repo holds only `settings.template.json`. The vault lives in dd_hub, not in the repo.
* Any environment with workspace access gets the full settings.json, including keys.

### Verify the setup

* `echo $DD_HUB_ROOT` shows the mount path.
* The mount contains `episodes/`, `vault/`, `inputs/`, `audio/`, `video/`, `mosaics/`, `manims/`, `rules/`.
* `episodes/<N>/plan.json` is readable (for an existing episode).
* If the mount is unreachable, the apps fall back to the local cache with a loud warning (read-only); writes fail closed — they refuse rather than writing to a stale local copy.

### What NOT to do

* Do **not** use the Google Drive web API or a Drive plugin as the file store. API-level access is too slow and is not a local file path — the pipeline will not work with it. (Fine for one-off reads only.)
* Do **not** fake a local dd_hub folder (an empty local directory named dd_hub). The apps will write to it and the work will never reach the real workspace.
* Do **not** commit `settings.json` (or any file with API keys) to git.
* Do **not** set `DD_HUB_ROOT` to a path that isn't the mounted dd_hub folder.

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

#### 📌 Step 2: Clone the DDMA Repository inside WSL
In your WSL terminal, clone the repository into your native Linux home directory:
```bash
cd ~
git clone https://github.com/ashutoshmjain/ddma.git
cd ~/ddma
```

> 🔬 **Advanced / Local Testing Alternative (Working directly inside your existing Windows folder)**:
> If you already have DDMA on your Windows machine and want to test directly inside your existing Windows directory without cloning, you can navigate directly to your Windows drive (mounted inside WSL under `/mnt/c/`):
> ```bash
> cd /mnt/c/Users/ashut/OneDrive/Desktop/github/deepDive/ddma
> ```

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
cd ~/ddma
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
