// Editor's Preview Player Core Logic (Single-Player Consolidated Model)
let plan = [];
let timeline = [];
let currentGlobalTime = 0;
let totalDuration = 0;
let activeTimelineIndex = -1;
let isPlaying = false;
let lastTime = 0;
let animationFrameId = null;

// Audio Graph (Single video source channel)
let audioCtx = null;
let mainGainNode = null;
let currentVolume = 0.8;
let analyser = null;
let dataArray = null;
let bufferLength = 0;
let audioSource = null;

// UI Elements
const viewport = document.getElementById('viewport');
const ctx = viewport.getContext('2d');
const playBtn = document.getElementById('playBtn');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const volumeSlider = document.getElementById('volumeSlider');
const muteBtn = document.getElementById('muteBtn');
const seekTrack = document.getElementById('seekTrack');
const seekProgress = document.getElementById('seekProgress');
const seekHandle = document.getElementById('seekHandle');
const currentTimeLabel = document.getElementById('currentTimeLabel');
const totalTimeLabel = document.getElementById('totalTimeLabel');
const viewportStatus = document.getElementById('viewportStatus');
const clipsList = document.getElementById('clipsList');
const videoPlayer = document.getElementById('videoPlayer');

// Setup page resize constraints to preserve square aspect ratio
function resizeViewport() {
    const parent = viewport.parentElement;
    const size = Math.min(parent.clientWidth, parent.clientHeight, 740);
    viewport.width = size;
    viewport.height = size;
    drawFrame();
}

window.addEventListener('DOMContentLoaded', async () => {
    resizeViewport();
    window.addEventListener('resize', resizeViewport);
    await init();
    initUI();
});

// Load Plan and Setup Timeline
async function init() {
    try {
        const res = await fetch('plan.json');
        plan = await res.json();
    } catch (err) {
        console.error("Failed to load plan.json", err);
        return;
    }
    
    buildTimeline();
    renderSidebar();
    
    // Proactive load of actual video durations
    await loadVideoDurations();
}

// Build timeline structure: Video Clip -> Bridge Slide -> Video Clip
function buildTimeline() {
    timeline = [];
    let runningTime = 0;

    // Filter plan based on active mode (locked, unhidden)
    const filteredPlan = plan.filter(clip => {
        if (!clip.locked || clip.hidden) {
            return false;
        }
        // Video Mode excludes audio-only clips
        if (currentMode === 'video' && clip.audio_only) {
            return false;
        }
        return true;
    });

    filteredPlan.forEach((clip, index) => {
        // 1. Add Bridge Card slide between clips (Video Mode Only)
        if (currentMode !== 'audio' && index > 0 && clip.bridge_text && clip.bridge_text.length > 0) {
            timeline.push({
                type: 'bridge',
                text: clip.bridge_text[0],
                duration: 5.0,
                startGlobal: runningTime,
                endGlobal: runningTime + 5.0,
                clipNum: clip.num
            });
            runningTime += 5.0;
        }

        // 2. Add Video Clip segment
        const isAudioOnly = clip.audio_only === true;
        const clipSrc = isAudioOnly 
            ? `/previews/preview_episode_244_${clip.num}.mp3`
            : `/docs/assets/clips/244-${clip.num}.mp4`;

        timeline.push({
            type: 'video',
            clipNum: clip.num,
            title: clip.title,
            duration: 10.0, // Temporary fallback, overwritten later
            startGlobal: runningTime,
            endGlobal: runningTime + 10.0,
            src: clipSrc
        });
        runningTime += 10.0;
    });

    updateTotalDuration();
}

function updateTotalDuration() {
    totalDuration = timeline.length > 0 ? timeline[timeline.length - 1].endGlobal : 0;
    totalTimeLabel.textContent = formatTime(totalDuration);
}

// Probes metadata of video clips asynchronously
async function loadVideoDurations() {
    let runningTime = 0;
    const validatedTimeline = [];

    for (let i = 0; i < timeline.length; i++) {
        const item = timeline[i];
        if (item.type === 'video') {
            try {
                let duration = await getVideoDuration(item.src);
                const clipInfo = plan.find(c => c.num === item.clipNum);
                
                // Use calculated segments fallback if metadata returns invalid duration
                if (isNaN(duration) || duration <= 0) {
                    const baseDur = calculateClipDuration(clipInfo);
                    duration = baseDur + (currentMode === 'audio' ? 0.0 : 2.0);
                } else {
                    // Subtract 2.0s title card intro in audio preview mode
                    const isAudioOnly = clipInfo && clipInfo.audio_only === true;
                    if (currentMode === 'audio' && !isAudioOnly) {
                        duration = Math.max(0, duration - 2.0);
                    }
                }
                
                item.duration = duration;
                item.startGlobal = runningTime;
                item.endGlobal = runningTime + item.duration;
                runningTime += item.duration;
                validatedTimeline.push(item);
            } catch (err) {
                console.warn(`Could not probe duration for ${item.src}, using fallback:`, err);
                const clipInfo = plan.find(c => c.num === item.clipNum);
                
                if (currentMode === 'video') {
                    // Exclude clip if the video file does not exist in video mode
                    console.warn(`Excluding missing video file: ${item.src}`);
                } else {
                    // Fall back to segment math in Audio Mode
                    const baseDur = calculateClipDuration(clipInfo);
                    item.duration = baseDur;
                    item.startGlobal = runningTime;
                    item.endGlobal = runningTime + item.duration;
                    runningTime += item.duration;
                    validatedTimeline.push(item);
                }
            }
        } else if (item.type === 'bridge') {
            item.startGlobal = runningTime;
            item.endGlobal = runningTime + item.duration;
            runningTime += item.duration;
            validatedTimeline.push(item);
        }
    }

    timeline = validatedTimeline;
    updateTotalDuration();
    renderSidebar();
    seekTo(0);
}

function getVideoDuration(src) {
    return new Promise((resolve, reject) => {
        const tempVideo = document.createElement('video');
        tempVideo.src = src;
        tempVideo.preload = 'metadata';
        
        tempVideo.onloadedmetadata = () => {
            resolve(tempVideo.duration);
        };
        
        tempVideo.onerror = () => {
            reject(new Error(`Failed to load metadata for ${src}`));
        };
        
        tempVideo.load();
    });
}

function calculateClipDuration(clip) {
    let total = 0;
    if (clip && clip.segments) {
        clip.segments.forEach(seg => {
            total += parseFloat(seg.duration) || 0;
        });
    }
    return total;
}

// Render Left Sidebar Selection Grid
function renderSidebar() {
    clipsList.innerHTML = '';
    
    // Map list of plan clips that are active in timeline
    const activeClips = plan.filter(clip => {
        return timeline.some(item => item.type === 'video' && item.clipNum === clip.num);
    });

    if (activeClips.length === 0) {
        clipsList.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); font-size: 0.85rem;">No active clips found. Lock clip cards in the dashboard.</div>';
        return;
    }

    activeClips.forEach(clip => {
        const videoItem = timeline.find(item => item.type === 'video' && item.clipNum === clip.num);
        if (!videoItem) return;
        
        const card = document.createElement('div');
        card.className = 'clip-item';
        card.id = `sidebar-clip-${clip.num}`;
        
        card.innerHTML = `
            <div class="clip-item-header">
                <span class="clip-item-title">CLIP ${clip.num}</span>
                <span class="clip-item-dur">${formatTime(videoItem.duration)}</span>
            </div>
            <div class="clip-item-desc">${clip.title || 'Untitled Segment'}</div>
        `;
        
        card.onclick = () => {
            seekTo(videoItem.startGlobal);
        };
        
        clipsList.appendChild(card);
    });
}

// Format Seconds into M:SS
function formatTime(sec) {
    const minutes = Math.floor(sec / 60);
    const seconds = Math.floor(sec % 60);
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
}

// Initialize UI Control bindings
let currentMode = 'video'; // 'video' | 'audio'
function initUI() {
    playBtn.addEventListener('click', togglePlay);
    prevBtn.addEventListener('click', playPrevious);
    nextBtn.addEventListener('click', playNext);
    
    volumeSlider.addEventListener('input', (e) => {
        setVolume(parseFloat(e.target.value));
    });
    
    muteBtn.addEventListener('click', toggleMute);
    
    // Seek tracking controls (Scrubbing)
    let isDragging = false;
    
    seekTrack.addEventListener('mousedown', (e) => {
        isDragging = true;
        handleSeekEvent(e);
    });
    
    window.addEventListener('mousemove', (e) => {
        if (isDragging) handleSeekEvent(e);
    });
    
    window.addEventListener('mouseup', () => {
        isDragging = false;
    });

    // YouTube-style seek tooltip tracking
    const seekTooltip = document.getElementById('seekTooltip');
    seekTrack.addEventListener('mousemove', (e) => {
        const rect = seekTrack.getBoundingClientRect();
        let pos = (e.clientX - rect.left) / rect.width;
        pos = Math.max(0, Math.min(1, pos));
        
        const hoverTime = pos * totalDuration;
        seekTooltip.textContent = formatTime(hoverTime);
        seekTooltip.style.opacity = '1';
        seekTooltip.style.left = `${pos * 100}%`;
    });
    
    seekTrack.addEventListener('mouseleave', () => {
        seekTooltip.style.opacity = '0';
    });

    // Mode Toggles
    const videoModeBtn = document.getElementById('videoModeBtn');
    const audioModeBtn = document.getElementById('audioModeBtn');
    
    videoModeBtn.addEventListener('click', async () => {
        if (currentMode === 'video') return;
        currentMode = 'video';
        videoModeBtn.classList.add('active');
        audioModeBtn.classList.remove('active');
        buildTimeline();
        await loadVideoDurations();
    });
    
    audioModeBtn.addEventListener('click', async () => {
        if (currentMode === 'audio') return;
        currentMode = 'audio';
        audioModeBtn.classList.add('active');
        videoModeBtn.classList.remove('active');
        initAudio(); // Initialize audio context immediately
        buildTimeline();
        await loadVideoDurations();
    });

    // Initial paint
    drawFrame();
}

function handleSeekEvent(e) {
    const rect = seekTrack.getBoundingClientRect();
    let pos = (e.clientX - rect.left) / rect.width;
    pos = Math.max(0, Math.min(1, pos));
    seekTo(pos * totalDuration);
}

// Web Audio API Setup (Consolidated Single Channel)
function initAudio() {
    if (audioCtx) return;
    
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass();
    
    mainGainNode = audioCtx.createGain();
    mainGainNode.gain.setValueAtTime(currentVolume, audioCtx.currentTime);
    
    // Wire up AnalyserNode for audio mode visualizer
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    bufferLength = analyser.frequencyBinCount;
    dataArray = new Uint8Array(bufferLength);
    
    mainGainNode.connect(analyser);
    analyser.connect(audioCtx.destination);
    
    // Route video element audio into AudioContext
    videoPlayer.muted = false;
    audioSource = audioCtx.createMediaElementSource(videoPlayer);
    audioSource.connect(mainGainNode);
}

// Toggle Play / Pause
function togglePlay() {
    initAudio();
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    
    if (isPlaying) {
        pause();
    } else {
        play();
    }
}

// Seek Timeline
function seekTo(globalTime) {
    currentGlobalTime = Math.max(0, Math.min(totalDuration, globalTime));
    updateTimelineState();
    syncVideoPlayback();
    updateSeekUI();
    drawFrame();
}

// Track active timeline segment and handle source loading
function updateTimelineState() {
    let newIndex = -1;
    for (let i = 0; i < timeline.length; i++) {
        if (currentGlobalTime >= timeline[i].startGlobal && currentGlobalTime < timeline[i].endGlobal) {
            newIndex = i;
            break;
        }
    }
    
    if (newIndex === -1 && timeline.length > 0) {
        newIndex = timeline.length - 1;
    }
    
    if (newIndex !== activeTimelineIndex) {
        activeTimelineIndex = newIndex;
        onTimelineItemChanged();
    }
}

function safeSetTimeAndPlay(videoEl, time) {
    const playVideo = () => {
        try {
            // Seek playhead only if difference is significant to avoid player stuttering
            if (Math.abs(videoEl.currentTime - time) > 0.3) {
                videoEl.currentTime = time;
            }
        } catch (e) {
            console.warn("Failed to set currentTime:", e);
        }
        
        if (isPlaying) {
            videoEl.muted = false;
            if (videoEl.paused) {
                videoEl.play().catch(err => console.log('Playback deferred:', err));
            }
        } else {
            if (!videoEl.paused) {
                videoEl.pause();
            }
        }
    };
    
    videoEl.onloadedmetadata = null;
    
    if (videoEl.readyState >= 1) {
        playVideo();
    } else {
        videoEl.onloadedmetadata = playVideo;
    }
}

function onTimelineItemChanged() {
    const item = timeline[activeTimelineIndex];
    if (!item) return;
    
    // Highlight sidebar card
    document.querySelectorAll('.clip-item').forEach(el => el.classList.remove('active'));
    const activeCard = document.getElementById(`sidebar-clip-${item.clipNum}`);
    if (activeCard) {
        activeCard.classList.add('active');
        activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    if (item.type === 'video') {
        // Change source of the single player if it's different
        if (videoPlayer.getAttribute('data-src') !== item.src) {
            videoPlayer.onloadedmetadata = null; // Clear callbacks to prevent event leaks
            videoPlayer.setAttribute('data-src', item.src);
            videoPlayer.src = item.src;
            videoPlayer.load();
        }
        
        const localTime = currentGlobalTime - item.startGlobal;
        const clipInfo = plan.find(c => c.num === item.clipNum);
        const isAudioOnly = clipInfo && clipInfo.audio_only === true;
        const playOffset = (currentMode === 'audio' && !isAudioOnly) ? 2.0 : 0.0;
        
        safeSetTimeAndPlay(videoPlayer, localTime + playOffset);
    }
}

// Keep physical HTML5 video nodes synchronized and handle crossfades/bridge overlays
function syncVideoPlayback() {
    const item = timeline[activeTimelineIndex];
    if (!item) return;
    
    if (item.type === 'video') {
        const localTime = currentGlobalTime - item.startGlobal;
        
        // Restore volume node
        if (mainGainNode && audioCtx) {
            mainGainNode.gain.setValueAtTime(currentVolume, audioCtx.currentTime);
        }
        
        // Find crossfade duration from plan.json
        const clipInfo = plan.find(c => c.num === item.clipNum);
        const crossfadeDuration = (clipInfo && clipInfo.crossfade !== undefined) ? clipInfo.crossfade : 0.0;
        
        let fade = 1.0;
        
        // Gapless transitions fade calculation
        if (crossfadeDuration > 0) {
            if (localTime < crossfadeDuration) {
                // Fade-in region
                fade = localTime / crossfadeDuration;
            } else if (localTime > item.duration - crossfadeDuration) {
                // Fade-out region
                fade = (item.duration - localTime) / crossfadeDuration;
            }
        }
        
        fade = Math.max(0, Math.min(1, fade));
        if (mainGainNode && audioCtx) {
            mainGainNode.gain.setValueAtTime(currentVolume * fade, audioCtx.currentTime);
        }
        
        const isAudioOnly = clipInfo && clipInfo.audio_only === true;
        const playOffset = (currentMode === 'audio' && !isAudioOnly) ? 2.0 : 0.0;
        
        safeSetTimeAndPlay(videoPlayer, localTime + playOffset);
    } else if (item.type === 'bridge') {
        const elapsed = currentGlobalTime - item.startGlobal;
        
        // Fade out preceding clip's tail over the 5-second slide duration
        const fade = Math.max(0, Math.min(1, 1.0 - (elapsed / 5.0)));
        if (mainGainNode && audioCtx) {
            mainGainNode.gain.setValueAtTime(currentVolume * fade, audioCtx.currentTime);
        }
        
        // Seek preceding clip's tail
        const prevVideoItem = activeTimelineIndex > 0 ? timeline[activeTimelineIndex - 1] : null;
        if (prevVideoItem) {
            const baseDur = prevVideoItem.duration;
            const targetSeek = Math.max(0, baseDur - 5.0) + elapsed;
            
            try {
                if (Math.abs(videoPlayer.currentTime - targetSeek) > 0.3) {
                    videoPlayer.currentTime = targetSeek;
                }
            } catch (e) {}
        }
        
        if (isPlaying) {
            videoPlayer.muted = false;
            if (videoPlayer.paused) {
                videoPlayer.play().catch(() => {});
            }
        } else {
            if (!videoPlayer.paused) {
                videoPlayer.pause();
            }
        }
    }
}

function play() {
    if (timeline.length === 0) return;
    isPlaying = true;
    playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    viewportStatus.textContent = 'Playing';
    
    lastTime = Date.now();
    animationFrameId = requestAnimationFrame(loop);
}

function loop() {
    if (!isPlaying) return;
    
    const now = Date.now();
    const dt = (now - lastTime) / 1000;
    lastTime = now;
    
    currentGlobalTime += dt;
    if (currentGlobalTime >= totalDuration) {
        currentGlobalTime = 0;
        seekTo(0);
        return;
    }
    
    updateTimelineState();
    syncVideoPlayback();
    updateSeekUI();
    drawFrame();
    
    animationFrameId = requestAnimationFrame(loop);
}

function playPrevious() {
    const threshold = 2.0; // seconds
    let activeItem = timeline[activeTimelineIndex];
    if (!activeItem) return;
    
    if (currentGlobalTime - activeItem.startGlobal > threshold) {
        seekTo(activeItem.startGlobal);
    } else {
        // Go back to previous video segment
        let prevVideoIndex = -1;
        for (let i = activeTimelineIndex - 1; i >= 0; i--) {
            if (timeline[i].type === 'video') {
                prevVideoIndex = i;
                break;
            }
        }
        if (prevVideoIndex !== -1) {
            seekTo(timeline[prevVideoIndex].startGlobal);
        } else {
            seekTo(0);
        }
    }
}

function playNext() {
    let nextVideoIndex = -1;
    for (let i = activeTimelineIndex + 1; i < timeline.length; i++) {
        if (timeline[i].type === 'video') {
            nextVideoIndex = i;
            break;
        }
    }
    if (nextVideoIndex !== -1) {
        seekTo(timeline[nextVideoIndex].startGlobal);
    }
}

// Update Seeker Progress UI
function updateSeekUI() {
    const percent = totalDuration > 0 ? (currentGlobalTime / totalDuration) * 100 : 0;
    seekProgress.style.width = `${percent}%`;
    seekHandle.style.left = `${percent}%`;
    currentTimeLabel.textContent = formatTime(currentGlobalTime);
}

// Mute and Volume Control
let isMuted = false;
function toggleMute() {
    initAudio();
    isMuted = !isMuted;
    if (isMuted) {
        muteBtn.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
        videoPlayer.muted = true;
    } else {
        muteBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
        videoPlayer.muted = false;
        setVolume(currentVolume);
    }
}

function setVolume(val) {
    initAudio();
    currentVolume = Math.max(0, Math.min(1, val));
    volumeSlider.value = currentVolume;
    
    if (!isMuted && mainGainNode && audioCtx) {
        mainGainNode.gain.setValueAtTime(currentVolume, audioCtx.currentTime);
    }
}

// Main Viewport Frame Painter (Canvas)
function drawFrame() {
    // Clear canvas
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    
    if (activeTimelineIndex === -1) {
        drawIntroScreen();
        return;
    }
    
    const item = timeline[activeTimelineIndex];
    
    if (currentMode === 'audio' && item.type === 'video') {
        drawAudioVisualizerScreen(item);
    } else {
        if (item.type === 'video') {
            // Check if the source clip is marked audio_only in the plan
            const clipInfo = plan.find(c => c.num === item.clipNum);
            if (clipInfo && clipInfo.audio_only) {
                // Keep the canvas solid black for audio only clips
                ctx.fillStyle = '#000000';
                ctx.fillRect(0, 0, viewport.width, viewport.height);
            } else {
                // Paint active video frame onto Canvas
                ctx.drawImage(videoPlayer, 0, 0, viewport.width, viewport.height);
            }
        } else if (item.type === 'bridge') {
            drawBridgeSlide(item.text);
        }
    }
}

function drawIntroScreen() {
    ctx.fillStyle = '#f1f3f9';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    ctx.font = '800 32px Outfit';
    ctx.fillText("Editor's Preview", viewport.width / 2, viewport.height / 2 - 20);
    
    ctx.font = '400 18px Outfit';
    ctx.fillStyle = '#8c9bb0';
    ctx.fillText('Click play to preview compiled timeline segments', viewport.width / 2, viewport.height / 2 + 20);
}

function drawBridgeSlide(text) {
    // Black background
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    
    // Wrap and center text lines on black slide
    const bridgeTextLines = wrapText(ctx, text, viewport.width - 120);
    const lineHeight = 46;
    const totalHeight = bridgeTextLines.length * lineHeight;
    let startY = (viewport.height - totalHeight) / 2 + lineHeight / 2;
    
    ctx.fillStyle = '#FFFFFF';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = 'bold 32px "Segoe UI"';
    
    bridgeTextLines.forEach((line) => {
        ctx.fillText(line, viewport.width / 2, startY);
        startY += lineHeight;
    });
}

function drawAudioVisualizerScreen(item) {
    // Draw dark radial gradient background
    const gradient = ctx.createRadialGradient(viewport.width/2, viewport.height/2, 50, viewport.width/2, viewport.height/2, viewport.width/2);
    gradient.addColorStop(0, '#111424');
    gradient.addColorStop(1, '#07090e');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    
    // Draw text info: active clip details
    ctx.fillStyle = '#f1f3f9';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    ctx.font = '800 24px Outfit';
    ctx.fillText('🎧 AUDIO PREVIEW MODE', viewport.width / 2, 80);
    
    ctx.font = '600 28px Outfit';
    ctx.fillStyle = '#a29bfe';
    ctx.fillText(`Clip ${item.clipNum}: ${item.title}`, viewport.width / 2, viewport.height / 2 - 120);
    
    // Draw live waveform wave using Web Audio Analyser data
    if (analyser && isPlaying) {
        analyser.getByteTimeDomainData(dataArray);
        
        ctx.lineWidth = 4;
        ctx.strokeStyle = 'rgba(162, 155, 254, 0.85)'; // glowing lavender
        ctx.shadowColor = '#6c5ce7';
        ctx.shadowBlur = 20;
        
        ctx.beginPath();
        const sliceWidth = viewport.width / bufferLength;
        let x = 0;
        
        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = (v * viewport.height / 2) + 20;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
            x += sliceWidth;
        }
        
        ctx.lineTo(viewport.width, viewport.height / 2 + 20);
        ctx.stroke();
        ctx.shadowBlur = 0; // reset shadow
        
        // Mirroring frequency bars at the bottom
        analyser.getByteFrequencyData(dataArray);
        const barWidth = (viewport.width / bufferLength) * 1.5;
        let barX = 0;
        ctx.fillStyle = 'rgba(108, 92, 231, 0.12)';
        
        for (let i = 0; i < bufferLength; i++) {
            const barHeight = (dataArray[i] / 255.0) * 100;
            ctx.fillRect(barX, viewport.height - barHeight - 40, barWidth - 2, barHeight);
            barX += barWidth;
        }
    } else {
        // Static visualizer text overlay when paused
        ctx.font = '500 18px Outfit';
        ctx.fillStyle = '#636e72';
        ctx.fillText(isPlaying ? 'Initializing visualizer...' : 'Press Play to start visualizer', viewport.width / 2, viewport.height / 2 + 80);
    }
}

// Canvas Text Wrapping Utility
function wrapText(context, text, maxWidth) {
    const words = text.split(' ');
    const lines = [];
    let currentLine = '';
    
    for (let n = 0; n < words.length; n++) {
        let testLine = currentLine + words[n] + ' ';
        let metrics = context.measureText(testLine);
        let testWidth = metrics.width;
        if (testWidth > maxWidth && n > 0) {
            lines.push(currentLine.trim());
            currentLine = words[n] + ' ';
        } else {
            currentLine = testLine;
        }
    }
    lines.push(currentLine.trim());
    return lines;
}
