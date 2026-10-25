# DDMA Clips & Motion Graphics Design Principles
## The Dual-Channel Clips Architecture: Mosaic Square vs. Standalone Infographics

> [!NOTE]
> This document formalizes the updated architecture for short-form clips in DDMA, incorporating the proven design principles from the 1080p long-form video engine evolution. It establishes two distinct, dedicated production pipelines:
> 1. **Path A (Send to Mosaic)**: 1080×1080 caption-free square video feeder with matching 1080×1080 intro/outro cards.
> 2. **Path B (Infographic Button)**: Standalone 1080×1920 (9:16 vertical reel) motion graphics engine directly inspired by the long-form video system.

---

## 1. The Core Creative Philosophy: "Holding Attention Over Minimizing Compute"

In automated content production, there is a recurring temptation to optimize for rendering speed (e.g. downsampling, cutting vector frames, reusing static slides). **We reject this compromise.**

> [!IMPORTANT]
> **The Golden Rule**: A clip that renders in 10 seconds but loses the viewer’s visual attention in 3 seconds is worthless. A clip that takes 60 seconds to render but holds deep, uninterrupted intellectual attention from the first second to the last is a viral asset. Always optimize for **visual retention, typographic precision, and kinetic narrative flow**.

---

## 2. The Dual-Channel Clips Pipeline

```
                              [ Raw Episode Audio & Transcription ]
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │      DDMA Clip Curator Deck (Port 8000)   │
                         └─────────────────────┬─────────────────────┘
                                               │
                   ┌───────────────────────────┴───────────────────────────┐
                   ▼                                                       ▼
      [ Channel 1: Send to Mosaic ]                            [ Channel 2: Infographic Button ]
   ┌────────────────────────────────┐                      ┌───────────────────────────────────────┐
   │ • 1:1 Square (1080×1080 Native)│                      │ • 9:16 Vertical Reel (1080×1920 Native│
   │ • Strictly CAPTION-FREE        │                      │ • In-House Standalone Motion Engine   │
   │ • Fills Mosaic graphic box     │                      │ • Single-line Top Caption Ribbon      │
   │ • 1080×1080 Intro/Outro Cards  │                      │ • Holographic Host Nodes (Satosha/i)  │
   │ • Upgraded from legacy 740×740 │                      │ • Living Soundscape Orbital Backdrop  │
   │ • Clean vector motion graphics │                      │ • Kinetic Visual Metaphors            │
   │ • External compositing in      │                      │ • 5s Sustained Speech Hysteresis      │
   │   Mosaic timeline template     │                      │ • Bottom 72-Bar Audio Spectrum        │
   └────────────────────────────────┘                      └───────────────────────────────────────┘
```

---

## 3. Path A: The Mosaic Feeder Pipeline (1080×1080 Square)

### Role & Purpose:
- Feeds into Mosaic's external video editor and social reel automation.
- Fills the designated square graphic box within Mosaic's vertical templates without pixelation, blur, or letterboxing.

### Resolution & Upgrades:
- **Upgraded from Legacy 740×740**: We now render natively at **1080×1080 Full HD Square**.
  - Eliminates the blur caused by upscaling a 740px canvas inside 1080p vertical templates.
  - Razor-sharp vector typography, coordinate axes, and orbital rings.
- **Strictly Caption-Free**:
  - The 1080×1080 square graphic contains **zero subtitles or caption ribbons**, avoiding conflicts with Mosaic's native caption burning engine.
- **Matching 1080×1080 Intro & Outro Cards**:
  - Intro card: High-impact dark minimalist episode badge with episode number, topic slug, and animated entrance.
  - Outro card: Call-to-action card (Spotify, deepdive.shutri.com, YouTube) formatted in native 1080×1080.
  - Concat/xfade transitions happen seamlessly in the 1080×1080 domain.

---

## 4. Path B: The Standalone Infographic Pipeline (1080×1920 Tall Video)

### Role & Purpose:
- End-to-end standalone motion graphics reels generated entirely in-house with zero external dependencies.
- One-click publishing for TikTok, Instagram Reels, and YouTube Shorts.

### Design Architecture (Inherited from Long-Form Engine):

#### 1. Earmarked Vertical Canvas Zones (1080×1920)
- **Top Safe Header & Topic Slug**: $y = 100 \dots 240$
- **Top Single-Line Caption Ribbon**: $y = 260 \dots 380$
  - Word-level active spotlight: **Radiant Gold** (`#ffd60a`).
  - Spoken words passed: **Pure White** (`#f8fafc`).
  - Upcoming words: **Muted Dim Slate** (`#64748b`).
  - **Zero bounding boxes or borders** around active words.
- **Top-Flank Holographic Host Nodes**: $y \approx 200$, flanking the upper edges:
  - **Satosha** (Male, Left Flank, Cyan `#00e5ff`).
  - **Satoshi** (Female, Right Flank, Gold `#ffd60a`).
  - **5-Second Sustained Speech Hysteresis**: Ignores short interjections (*"aha"*, *"yeah"*, *"right"*); only switches when a host sustains speech for $\ge 5.0$ seconds.
- **Middle Visual Hero Stage**: $y = 420 \dots 1480$ (Dedicated 1060px high canvas)
  - **Kinetic Visual Metaphors**: Simple moving diagrams that unfold in direct sync with the spoken narrative (e.g. animated walking robot in wilderness, tipping balance scales, dynamic token equilibrium curves).
  - **Sparse, High-Impact Quotes & Formulas**: Quotes and equations are used sparingly as punchline anchors (rate-limited, no information overload).
- **Audio Spectrum Visualizer**: $y = 1520 \dots 1680$ (Responsive kinetic equalizer micro-bars).
- **Platform Safe Zone**: $y > 1700$ (Kept clean for mobile platform UI: like button, comments, sound attribution).

#### 2. The Living Soundscape Backdrop
- 3 concentric orbital rings with orbiting satellite nodes running in continuous subtle rotation.
- Guarantees that **no frame is ever static**, preventing viewers from swiping away during pauses.

---

## 5. Comparative Pipeline Specification Table

| Architectural Feature | Path A: Mosaic Feeder | Path B: Standalone Infographic |
| :--- | :--- | :--- |
| **Primary Target** | External Mosaic Timeline | TikTok, IG Reels, YouTube Shorts |
| **Aspect Ratio & Resolution** | **1:1 Square (1080×1080)** | **9:16 Vertical (1080×1920)** |
| **Legacy Format Replaced** | 740×740 (Deprecated) | N/A (Direct Native Layout) |
| **Captions / Subtitles** | **None** (Mosaic handles burning) | Top single-line word-level spotlight |
| **Intro / Outro Cards** | Native 1080×1080 Vector Cards | Embedded top/bottom branding |
| **Host Avatar Nodes** | None (clean graphic) | Top-flank holographic nodes (Cyan / Gold) |
| **Speech Diarization** | Not required | YIN tracking + 5s sustained hysteresis |
| **Visual Content** | High-density vector diagrams | Kinetic narrative metaphors + Living Soundscape |
| **Bottom Equalizer** | None (or optional base ribbon) | 72-bar kinetic audio spectrum ($y \approx 1600$) |

---

## 6. Technical Implementation Action Plan

### Step 1: Upgrading DDMA Engine Square Resolution (`740` $\to$ `1080`)
- In [`ddma/ddma.py`](file:///c:/Users/ashut/OneDrive/Desktop/github/ddma/ddma.py):
  - Change default canvas dimensions from `740×740` to `1080×1080`.
  - Update FFmpeg color source filters from `s=740x740` to `s=1080x1080`.
  - Update `wrap_text_outro` and intro/outro card generators to format for 1080×1080 with adjusted margins and font sizes.
- In [`ddma/infographic_engine.py`](file:///c:/Users/ashut/OneDrive/Desktop/github/ddma/infographic_engine.py):
  - Standardize default render target to `1080×1080`.

### Step 2: Infographic Button Pipeline Standardization
- Connect the **Infographic** compilation action in `ddma/curator.html` and `ddma/scratch/run_curator.py` to the perfected 1080×1920 vertical engine layout.
- Ensure the top-flank host avatar nodes ($y = 135$ horizontal or vertical safe equivalent), 5-second sustained speech rule, and kinetic archetypes (`robot_wilderness_fallacy`, `economic_equilibrium_matrix`, etc.) are shared across both long-form and clip generation.

### Step 3: Verification & Test Runs
- Render a 1080×1080 square test clip with intro/outro cards to verify Mosaic compatibility.
- Render a 1080×1920 standalone vertical infographic reel to verify mobile UI safe margins and kinetic pacing.
