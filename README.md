# DeepDive Media Automator (DDMA)

DeepDive Media Automator (DDMA) is a python CLI toolkit and an interactive web curator dashboard designed to transcribe long podcast episodes, curate high-engagement clips with sample-accurate word boundaries, mix sound/music stings, and compile ready-to-publish video assets for TikTok, Instagram Reels, and YouTube Shorts.

---

## 🌌 Key Features

* **Multi-Project Management**: Curate multiple episodes side-by-side. The dashboard manages local audio files, word-level Whisper transcripts, and clip plans in project-specific workspaces.
* **Collapsible & Resizable IDE-style Layout**: Drag dividers to adjust transcription/clips real estate. Collapse the sidebar to maximize focus.
* **Word-Level Curation & Timeline Snapping**: Left-click or right-click transcript words to set precise sub-second boundaries. Highlights used ranges to prevent overlapping selections.
* **Per-Segment Music Volume Mixer**: Mix background music stings. Set individual duration, crossfade transition, and custom volume level multipliers (e.g. `0.20` for subtle background ducking).
* **Global Sting Manager**: Upload new music stings directly through the settings panel to make them globally available. Delete or clean up custom tracks on the fly.
* **Theme Customization**: Switch between **Nordic Breeze (Light)**, **Cyberpunk (Neon Cyan/Purple)**, and **Midnight (Dark default)**. Preferences persist across reloads.
* **Dynamic Media Exporters**:
  * **Audio (`.mp3`)**: Compiles mixed segments directly.
  * **Muxed Video (`.mp4`)**: Automatically overlays the mixed audio with a solid color canvas at custom resolutions (`740x740` square, `1080x1920` vertical reels, `1920x1080` landscape) and colors (presets or custom hex code).
* **Automatic Title Card Intro Prepending**: Pillow generates clean title cards with multi-line wrapping and joins them to the master clip using FFmpeg timescale normalization.

---

## 🛠️ Requirements

1. **Python 3.8+**
2. **OpenAI Whisper (`openai-whisper==20250625`)**
3. **FFmpeg**: Must be installed and added to your system's `PATH`.

### 🖥️ Recommended Hardware Configuration
Running AI transcription models (like OpenAI Whisper) is resource-intensive. For a smooth experience:
* **GPU (Highly Recommended)**: Dedicated NVIDIA GPU (GTX 1060 / RTX 2060 or better) with at least **4 GB VRAM** and CUDA support. Running Whisper on a CUDA-enabled GPU speeds up transcription by 10x–20x compared to CPU.
* **CPU**: Modern multi-core processor (Intel Core i5 / AMD Ryzen 5 or better).
* **RAM**: **16 GB RAM** or more is recommended.
* **Storage**: SSD (Solid State Drive) is highly recommended for faster reads/writes of large audio and video assets.

---

## 📥 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/deepdive-media-automator.git
   cd deepdive-media-automator
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🚀 How to Run the Curator GUI

Start the local server:
```bash
python scratch/run_curator.py
```
This automatically opens the dashboard in your default browser:
👉 **[http://localhost:8000/curator.html](http://localhost:8000/curator.html)**

### Workflow:
1. Put your raw podcast audio file in the repository root (e.g. `episode_244.m4a`).
2. Click **`➕ New Project`** in the Projects sidebar, give it a name, and select the source audio file.
3. Click **`Create & Transcribe`**. OpenAI Whisper will transcribe the file in the background (showing a live status spinner).
4. Once ready, select the project to load the word-level transcript and begin curating clips!
5. Add audio/music segments, customize volumes, preview compiles, and click **`Export Clip`** to output production-ready audio/video assets!
