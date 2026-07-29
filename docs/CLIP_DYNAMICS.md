# 🎬 DDMA Clip Dynamics & Feature Reference Guide

## 📌 Executive Overview
The **Clip** is the core functional building block of the **DeepDive Media Automator (DDMA)** progressive podcast production workflow. Each clip represents a high-engagement, standalone short-form asset (up to 2m 55s) tailored for social distribution (YouTube Shorts, Instagram Reels, TikTok) while collectively forming the baseline long-form podcast episode.

---

## 🎛️ Header Control Bar & Action Buttons

### 1. Clip Identifier & Title Editor
* **Badge (`245-1`)**: Color-coded clip number indicating Episode and Clip sequence.
* **Title Field**: Editable input for the social title card. Automatically constrained to two balanced lines for Instagram safe-zone compliance.
* **Expand/Collapse Arrow (`▼`)**: Accordion toggle to show or hide segment details.

### 2. Clip Attributes Bar
* **Duration (`MM:SS`)**: Calculated total duration of the concatenated audio segments.
* **Volume (`1.0`)**: Global output multiplier for the clip audio stream. Default is `1.0` (100%).
* **Crossfade (`0s`)**: Global crossfade duration applied across adjacent clip transitions.
* **Audio Only Checkbox**: When checked, skips video generation for audio-only export targets (e.g. Spotify baseline podcast).

---

## 🚀 Status & Action Trigger Buttons

| Button & Icon | State / Style | Function & Workflow Description |
| :--- | :--- | :--- |
| **`🎬 Intro`** | Amber (Uncompiled) / Green (Compiled) | Generates and previews the **2-second Title Card Intro slide** with charcoal background and white text layout. |
| **`🎬 Outro`** | Amber (Uncompiled) / Green (Compiled) | Generates and previews the **5-second Curiosity Question Outro slide** with a linear 5.0s audio fade-out. |
| **`▶ Audio`** | Bright Green Active | Plays sample-accurate concatenated clip audio (Intro Sting + Speech Audio + Outro Sting). |
| **`📹 Draft` / `📹 Video`** | Amber (`📹 Draft`) / Green (`📹 Video`) | **Pre-Mosaic (`📹 Draft`)**: Compiles 2s Title Card + Black Canvas Audio + 5s Outro slide.<br>**Post-Mosaic (`📹 Video`)**: Compiles 2s Title Card + Mosaic Motion Graphics + 5s Outro slide. |
| **`🌌 Mosaic`** | Disabled (Unlocked) / Enabled (Locked) | Triggers Mosaic external API to render motion infographics. **Cost-Protected**: Requires explicit card locking (`🔒 Locked`) to prevent accidental API invokes. |
| **`🤖 Remix`** | Disabled (Unlocked) / Enabled (Locked) | Triggers Gemini AI Co-Pilot to analyze and re-structure clip boundaries and titles. |
| **`🔓 Unlocked` / `🔒 Locked`** | Toggle Switch | Safety latch protecting expensive external API operations (Mosaic & Gemini Remix) and locking segment boundaries from accidental edits. |

---

## 🎵 Segment Dynamics (Audio, Music Stings, & Slides)

### 🎬 Intro Clip (Title Card Slide)
* **Duration**: Fixed `2.0s`.
* **Top Line**: Displays layout text (`EPISODE 245` or `EPISODE 245 • PART 1`).
* **Bottom Line**: Displays the curated clip title.

### 🎵 Music Segments (Intro/Outro Stings)
* **Sting Dropdown**: Select custom music files (`deepDive-soft-ok.mp3`, `Bluesy Vibes...mp3`).
* **Duration**: Configurable sting playback duration (typically 5.0s–5.5s).
* **Volume**: Default `1.0` (100% volume). Standalone stings play at full volume.
* **Crossfade**: Smooth crossfade overlap with adjacent speech audio (e.g. `1s` intro / `0.3s` outro).
* **Segment Controls**: `📋 Duplicate` and `🗑️ Delete` icons for reordering or removing stings.

### 🎙️ Audio Segment (Speech Track)
* **Speech Quote**: Verbatim Whisper transcription anchor text.
* **Duration**: Start/End time range (e.g., `110.62s`).
* **Sample-Accurate Slicing**: Re-encoded using FFmpeg (`-c:a libmp3lame -q:a 2`) to ensure clean word-boundary cuts without word clipping.

### 🌉 Outro Clip (Bridge Card Slide)
* **Duration**: Fixed `5.0s`.
* **Editable Curiosity Question**: Editable text field rendered in **Segoe UI Bold (34px)** centered on a solid black background.
* **Audio Track**: Fades out the last 5 seconds of preceding clip audio to prevent jarring cutoffs.
