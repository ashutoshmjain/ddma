# Architecture Guide & Canonical Asset Source Directory

## 📁 Source of Truth for Video and Audio Assets

All media assets (video, audio, infographics, and interactive cockpits) in this repository must reside **strictly under the src/ directory**.

### 1. Infographics Carousel Videos (src/vid/)
- **Path**: src/vid/
- **Purpose**: Canonical home for all standalone 740×740 square infographics MP4 videos embedded within mdBook publication chapters (e.g. src/vid/241-1-intro.mp4, src/vid/242-1-The-Tom-Cruise-Glitch.mp4, etc.).
- **Build Behavior**: mdbook build automatically compiles src/vid/ into ook/vid/ on every CI deployment.

### 2. DDMA Editor's Preview & Slopcast Audio Clips (src/ddma/docs/episodes/)
- **Path**: src/ddma/docs/episodes/<episode_number>/clips/
- **Purpose**: Stores the compiled MP4 segments and audio tracks for the DDMA visualizer and Slopcast audio player (e.g. src/ddma/docs/episodes/246/clips/246-1.mp4, 246-2.mp4, etc.).
- **Episode Plan Files**: src/ddma/docs/episodes/<episode_number>/plan.json
- **Episode Manifest**: src/ddma/docs/episodes.json

### 3. Static Web Build Pipeline
- **Command**: 
pm run build:pwa
  1. Compiles markdown & assets via mdbook build (src/ → ook/).
  2. Injects PWA service worker and copies src/ddma/docs/ to ook/ddma/docs/.
  3. Uploads ./book as the single unified web artifact to GitHub Pages (deepdive.shutri.com).

---

## 🚫 Rules for Agents & Developers
1. **NO Duplicate Asset Folders**: Never create or track duplicate media files in uild_temp/, ddma/docs/episodes/, ddma/clips/, or temporary root directories.
2. **Single Source of Truth**: When creating or updating any video or audio asset, write directly to src/vid/ or src/ddma/docs/episodes/.
3. **Git Tracking**: Ensure .gitignore ignores temporary build outputs (ook/, uild_temp/, ddma/scratch/) while explicitly preserving !src/ddma/docs/episodes/** and !src/vid/**.
