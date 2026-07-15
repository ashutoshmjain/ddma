# Roles and Responsibilities

This document defines the roles, responsibilities, and operational guidelines for the **DeepDive Media Automator (DDMA)** project workflow.

---

## 👥 Roles & Responsibilities

### 🧑‍💻 The User (Content Creator & Human Director)
*   **Audio Source**: Responsible for providing raw audio files (e.g., from NotebookLM).
*   **Intuitive Verification**: Responsible for verifying the output clips and videos from a human aesthetic and intuition standpoint (e.g., listening for cut quality, verifying word boundary transitions).
*   **Guidance & Steering**: Provides feedback, direction, and creative suggestions to refine clip markers or video specifications.

### 🤖 The Agent (Developer & Automated Tester)
*   **Automated Execution**: Executes commands in the background on behalf of the user to transcribe, segment, and render videos.
*   **Script Iteration**: Responsible for acting as the developer/tester to build, debug, and iteratively improve the DDMA script until it is bug-free.
*   **Controlled Mode Transitions**: **CRITICAL**: Only act in "Developer" or "Tester" mode when the user explicitly requests it. Otherwise, focus on serving as the executor/orchestrator of the existing script.
*   **Muxing Focus**: Generate video assets selectively (one clip at a time) to ensure the user can focus and review without cognitive overload.
*   **Automatic Command Execution**: Always execute python scripts using the direct path to the executable (`C:\Users\ashut\AppData\Local\Programs\Python\Python312\python.exe`) instead of raw `python` to run them automatically without requiring manual permission approval.

---

## 🛠️ Script Design Rules & Constraints

When developing or executing segmentation tasks, the agent must enforce the following technical constraints:
1.  **Duration Limit**: No clip may exceed **2 minutes and 55 seconds** (to prevent YouTube Shorts or Instagram Reels from rejecting them).
2.  **Sample-Accurate Slicing**: Always re-encode audio during cuts (`-c:a libmp3lame -q:a 2`) instead of stream copying to prevent word splitting at boundaries.
3.  **Selective Forward Chronology**: Identify and plan high-engagement thematic concepts in forward chronological order (no requirement to cover the entire timeline sequentially). Focus on standalone clip integrity.
4.  **Dynamic Black Canvas Muxing (Mosaic Drafts)**: Automatically mux audio clips with a solid black (`0, 0, 0`) `740x740` background video generated in-memory via FFmpeg's `color` filter (no external files required). This creates the raw draft (`clips/<episode>-<num>.mp4`) for Mosaic.
5.  **Title Card Music**: Prepend title cards (typically 2 seconds) using the custom audio file `title-card-music.mp3` as the audio track instead of silent audio (`anullsrc`), ensuring audio profiles (sample rates, layouts) are correctly matched during concatenation.
6.  **Dynamic Title Card Intro Prepending**: For finished clips from Mosaic, dynamically generate a matching title card image in Python/Pillow on a charcoal background, render it as a 2-second intro matching the master's properties, and concatenate them losslessly directly to the start of the master clip:
    *   **Part 1 Exception**: The title card for Part 1 shows `EPISODE [X]` on the top line and the full episode title on the bottom line (the clip-specific title is hidden).
    *   **Part 2+ Layout**: Shows `EPISODE [X] • PART [Y]` on the top line and the clip title on the bottom line.
    *   **Multi-Line Layout**: Titles are automatically split into two balanced lines to stay inside the Instagram safe zone. If the title contains explicit `\n` characters in `plan.json`, the script splits the text exactly at those positions (e.g., to force a 3-line format).
7.  **Audio/Video Stream Duration Equalization**: Before compiling or combining video clips, always equalize their video and audio stream durations (by trimming the longer stream to match the duration of the shorter stream). This prevents cumulative audio/video desync or drift during concatenation and satisfies publishing requirements (e.g. Spotify's error regarding mismatched video/audio track lengths).
8.  **Narrative Bridge Cards**: Insert 5.0-second black transition slides containing one single bold curiosity-provoking question between clips to preserve storyboard continuity. The texts are editable under the `"bridge_text"` key in `plan.json`. Text is rendered in **Segoe UI Bold (`34px`)** in white, fully centered on a black background. The slide audio is the final 5.0s of audio extracted from the preceding clip, linearly faded out, to prevent abrupt silences.
9.  **Timebase Normalization**: When crossfading intro/outro streams using FFmpeg's `xfade`, apply `[in]settb=1/90000[out]` to both input streams to prevent timescale mismatch errors (specifically when combining Remotion-exported assets with custom PIL renders).
10. **Welcome Music Restriction**: The welcome music stings (`deepDive-soft-ok.mp3` and `deepDive-strong.mp3`) represent introductory/welcome sounds for the podcast. They must ONLY be used in the first or second clip of the entire episode (Clip 1 or Clip 2). Under no circumstances may they be used in Clip 3 or any subsequent clips, to avoid repeating welcome sounds to the audience.

---

## 🔄 The End-to-End Media Automation Pipeline

Below is the step-by-step operational workflow for processing podcast episodes, from a raw audio file to final social media clips:

### 1. Transcribe
*   **Command**: `powershell -Command "python ddma.py transcribe --audio <episode>.mp3"`
*   **Action**: Transcribes the long audio file using OpenAI Whisper (`tiny.en` by default) with native word-level timestamps (`word_timestamps=True`) enabled.
*   **Output**: Creates a `transcription.json` file containing start/end timestamps for every spoken word.

### 2. Plan
*   **Action**: Analyze the transcription to find high-engagement concepts, metaphors, and logical statements. Select specific target ranges (typically between 90 and 165 seconds).
*   **Command**: `powershell -Command "python ddma.py plan --audio <episode>.mp3 --ranges '<start>-<end>, <start>-<end>'"` (or generate the `plan.json` programmatically).
*   **Output**: Generates a `plan.json` containing the curated clips with titles and snapped start/end times.

### 3. Title Curating
*   **Action**: Open `plan.json` and curate or manually refine the `"title"`, snap boundaries, and add `"bridge_text"` lists of questions for transitions.

### 4. Audio Slice
*   **Command**: `powershell -Command "python ddma.py cut --audio <episode>.mp3 --plan-file plan.json --out-dir clips"`
*   **Action**: Splits the long audio into sample-accurate MP3 clip slices. Start times are adjusted to strip leading silence and conversational disfluencies in the first 2 seconds. End times are trimmed tightly right after the last spoken word.
*   **Output**: Saves clips to `clips/` named with their title (e.g., `clips/243-1-Memory vs Healing Trade-off.mp3`).

### 5. Draft Mux
*   **Command**: `powershell -Command "python ddma.py mux-clip --num <clip_number>"`
*   **Action**: Merges the audio clip with a dynamically generated solid black `740x740` background video.
*   **Output**: Saves the draft video directly to `clips/<episode>-<num>.mp4` (e.g., `clips/243-1.mp4`).

### 6. Infographic Overlay (Mosaic)
*   **Action**: Import the draft `clips/<episode>-<num>.mp4` video into Mosaic to add infographics and visual graphics. Use Mosaic's timeline to trim any remaining millisecond-level room tone silence at the end to ensure the video loops seamlessly when auto-played on Instagram/TikTok.
*   **Output**: Export the finished animation, overwriting the file at `clips/<episode>-<num>.mp4`.

### 7. Add Intro
*   **Command**: `powershell -Command "python ddma.py compile-clip --num <clip_number>"`
*   **Action**: Automatically:
    1. Backs up the master clip to `clips/<episode>-<num>-original.mp4`.
    2. Loads the title and formatting from `plan.json`.
    3. Normalizes and equalizes the master clip's video and audio stream durations.
    4. Dynamically generates the title card image (with Part 1 exception, two-line wrapping, or explicit newlines).
    5. Probes the master clip properties and renders a 2-second intro matching them exactly.
    6. Losslessly concatenates the intro and normalized master clip with a 1-second crossfade (using `settb=1/90000`).
*   **Output**: Overwrites `clips/<episode>-<num>.mp4` with the final compiled video.

### 8. Combine Episode
*   **Command**: `powershell -Command "python scratch/combine_clips_demuxer.py"`
*   **Action**: Reads `plan.json` to generate 5.0-second text-based question cards (overlaying a fade-out of the preceding music) for transitions, and concatenates all clips and bridge cards in order. Applies re-encoding to force constant 30 fps and uniform 48 kHz stereo audio.
*   **Output**: Generates a unified `combined_<episode>.mp4` video with perfectly aligned audio and video streams.

