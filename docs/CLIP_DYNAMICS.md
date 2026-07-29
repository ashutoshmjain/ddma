# 🎬 DDMA Clip Dynamics - Master Reference & Technical Specification Guide

## 📌 1. Executive Summary & Purpose

The **Clip** is the core functional building block of the **DeepDive Media Automator (DDMA)** progressive podcast production engine. In the DDMA paradigm, unedited raw multi-hour audio is transformed into standalone, high-engagement short-form video assets (up to 2 minutes 55 seconds) for social platforms (YouTube Shorts, Instagram Reels, TikTok) while simultaneously forming the baseline long-form podcast episode.

### 🎯 Dual-Purpose Architecture of This Document
This document is designed as the **definitive reference standard** for two target audiences:
1. **End-Users / Content Directors**: Step-by-step visual UI guide, interactive controls, transcript boundary selection workflows, lock safety latches, and sting volume rules.
2. **AI Agents & Software Developers**: Complete technical specification detailing API endpoints, JSON data contracts (`plan.json`), FFmpeg rendering pipelines, DOM selectors, and automated E2E test assertions (`scratch/test-env/test_curator.js`).

---

## 🎛️ 2. UI Layout & Visual Anatomy

Each Clip Card in the Curator interface (`curator.html`) consists of four primary structural regions:

```
+---------------------------------------------------------------------------------------------------------+
| [▼] [245-1]  Title Editor Input                                                                        |
| Duration: 02:07 | Volume: 1.0 | Crossfade: 0s | [ ] Audio Only                                          |
| [🎬 Intro] [🎬 Outro] [▶ Audio] [📹 Draft/Video] [🌌 Mosaic] [🤖 Remix] [🔓 Unlocked / 🔒 Locked]      |
+---------------------------------------------------------------------------------------------------------+
| 🎬 Intro Clip (Title Card Slide)                                                   Duration: 2.0s       |
| 🎵 Music Segment (Intro Sting)                                                     Duration: 5.0s       |
| 🎙️ Audio Segment (Speech Track) [Double-Click to Edit Boundaries]                   Duration: 110.62s    |
| 🎵 Music Segment (Outro Sting)                                                     Duration: 5.5s       |
| 🌉 Outro Clip (Bridge Card Slide - Editable Question)                               Duration: 5.0s       |
+---------------------------------------------------------------------------------------------------------+
```

---

## 🖱️ 3. Interactive Workflows & User Controls

### 🎙️ Transcript Boundary Selection via Double-Click
The primary mechanism for refining audio boundaries is interactive transcript snapping:

* **Trigger**: Double-click on any `.segment-row.audio-seg` row.
* **Unlocked State (`🔓 Unlocked`)**:
  1. Instantly triggers audio snippet preview (`playAudioRange(start, end)`).
  2. Automatically expands the right-side **Transcript Panel** (`ensureTranscriptPanelExpanded()`).
  3. Highlights spoken word-level timestamps in the transcript corresponding to the current speech segment.
  4. Clicking any word in the transcript automatically snaps that word's exact Whisper timestamp as the new `start` or `end` boundary for the segment.
* **Locked State (`🔒 Locked`)**:
  * Triggers audio snippet preview, but **freezes transcript boundary selection** to protect finalized clips from accidental timestamp mutations.

---

### 🎵 Music Segment Double-Click Snippet Preview
* **Trigger**: Double-click on any `.segment-row.music-seg` row.
* **Behavior**: Instantly plays a standalone preview of the selected music sting file (`playMusicSegment(file, duration, volume)`), using the exact sting duration and volume setting (`default: 1.0`).

---

### 🔒 Cost-Protection Safety Latch (`🔓 Unlocked` vs `🔒 Locked`)

To protect creators against accidental billing from external cloud services, DDMA enforces a strict safety latch:

| Card State | Boundary & Title Editing | External API Buttons (`🌌 Mosaic`, `🤖 Remix`) | Video Preview (`📹 Draft` / `📹 Video`) |
| :--- | :--- | :--- | :--- |
| **`🔓 Unlocked`** | **Enabled** (Editable text, boundary snapping, segment reordering) | **DISABLED** (Grayed out to prevent accidental API charges) | **Enabled** (Compiles Pre-Mosaic Draft video) |
| **`🔒 Locked`** | **Frozen** (Protected against accidental clicks) | **ENABLED** (Allows intentional invoke of Mosaic & Gemini Remix) | **Enabled** (Compiles Post-Mosaic Master video if rendered) |

---

## 🚀 4. Render Pipeline & Video Status Dynamics

DDMA distinguishes between Pre-Mosaic draft baselines and Post-Mosaic final master videos:

```
[Audio Slicing] ---> [Pre-Mosaic Draft] ---> [Mosaic Motion Graphics] ---> [Post-Mosaic Master]
                         (📹 Draft)                                             (📹 Video)
```

| Pipeline Stage | Button Badge | Video Composition & Rendering Engine | Video Modal Banner & Subtitle |
| :--- | :--- | :--- | :--- |
| **Pre-Mosaic Baseline** | **`📹 Draft`** *(Amber Badge)* | **2s Title Card Intro** + **740x740 Solid Black Canvas Audio** + **5s Curiosity Question Outro** | **`📹 DRAFT BASELINE (Pre-Mosaic) - Part X: <Title>`**<br>`ℹ️ Pre-Mosaic Draft Baseline (2s Title Card + Black Canvas Audio + 5s Outro). Lock clip & run Mosaic for motion infographics.` |
| **Post-Mosaic Master** | **`📹 Video`** *(Bright Green Badge)* | **2s Title Card Intro** + **Mosaic Motion Graphics Video** + **5s Curiosity Question Outro** | **`📹 FINAL MASTER VIDEO (Post-Mosaic) - Part X: <Title>`**<br>`✨ Master Video with Motion Graphics • clips/<project>-<num>.mp4` |

---

## 🛠️ 5. Technical Specifications & Developer Contract

### 📄 `plan.json` Clip Object Schema

```json
{
  "num": 1,
  "title": "Ground breaking new research on nature of Singularity !",
  "start": 0.0,
  "end": 110.62,
  "locked": false,
  "music": "deepDive-soft-ok.mp3",
  "music_volume": 1.0,
  "bridge_text": [
    "Thanks for tuning in as we prep the full episode - one clip at a time :-)"
  ],
  "segments": [
    {
      "type": "music",
      "music_file": "deepDive-soft-ok.mp3",
      "duration": 5.0,
      "volume": 1.0,
      "crossfade": 1.0
    },
    {
      "type": "audio",
      "start": 0.0,
      "end": 110.62,
      "duration": 110.62,
      "volume": 1.0,
      "crossfade": 0.0,
      "text": "Episode 245"
    },
    {
      "type": "music",
      "music_file": "Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3",
      "duration": 5.5,
      "volume": 1.0,
      "crossfade": 0.3
    }
  ]
}
```

---

### 🌐 HTTP API Endpoints (`scratch/run_curator.py`)

* **`POST /compile-clip?id=<project_id>&num=<clip_num>`**:
  * Triggers `ddma.py compile-clip --num <clip_num> --plan-file projects/<project_id>/plan.json`.
  * Auto-selects the newest sliced audio MP3 matching the clip number.
  * Equalizes audio and video stream durations using FFprobe.
  * Returns `{"success": true, "message": "Compilation completed successfully."}`.

---

### 🧪 Automated E2E Test Assertion Matrix (`scratch/test-env/test_curator.js`)

All automated test suites must validate the clip dynamics contract defined in this document:

```javascript
// TEST 2b: Verifying Safety Latch & Button Availability
// Unlocked Clip -> Mosaic Button Disabled
assert(unlockedClip.mosaicButton.disabled === true);
// Locked Clip -> Mosaic Button Enabled
assert(lockedClip.mosaicButton.disabled === false);

// TEST 5: Duration & Stream Alignment Verification
assert(abs(videoDuration - audioDuration) <= 0.05);

// TEST 6: On-Demand Compilation & Green-Out Status
assert(videoButton.classList.contains('btn-status-success'));
```
