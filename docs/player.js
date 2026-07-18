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
let useWebAudio = false; // Start with native playback for Video Mode to bypass browser constraints

// UI Elements
const viewport = document.getElementById('viewport');
const ctx = viewport.getContext('2d');
const playBtn = document.getElementById('playBtn');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const volumeSlider = document.getElementById('volumeSlider');
const muteBtn = document.getElementById('muteBtn');
const skipBackBtn = document.getElementById('skipBackBtn');
const skipForwardBtn = document.getElementById('skipForwardBtn');
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

window.addEventListener('DOMContentLoaded', () => {
    resizeViewport();
    window.addEventListener('resize', resizeViewport);
    initUI();
    init();
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
            ? `/previews/preview_episode_244_${clip.num}.mp3?v=3`
            : `/docs/assets/clips/244-${clip.num}.mp4?v=3`;

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
            <div class="clip-item-row1">
                <span>CLIP ${clip.num}</span>
                <span class="clip-duration">${formatTime(videoItem.duration)}</span>
            </div>
            <div class="clip-meta-title">${clip.title || 'Untitled Segment'}</div>
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
    skipBackBtn.addEventListener('click', skipBackward);
    skipForwardBtn.addEventListener('click', skipForward);
    
    volumeSlider.addEventListener('input', (e) => {
        setVolume(parseFloat(e.target.value));
    });
    
    // Explicitly enforce CORS flag in JavaScript
    videoPlayer.crossOrigin = "anonymous";
    
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
        useWebAudio = true; // Enable Web Audio for visualizer
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

// Web Audio API Setup (Consolidated Single Channel with Native Fallback)
function initAudio() {
    if (audioCtx || !useWebAudio) return;
    
    try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContextClass();
        
        mainGainNode = audioCtx.createGain();
        mainGainNode.gain.value = currentVolume;
        
        // Wire up AnalyserNode for audio mode visualizer
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        bufferLength = analyser.frequencyBinCount;
        dataArray = new Uint8Array(bufferLength);
        
        mainGainNode.connect(analyser);
        analyser.connect(audioCtx.destination);
        
        // Route video element audio into AudioContext (ALWAYS unmuted natively when routing!)
        videoPlayer.muted = false;
        audioSource = audioCtx.createMediaElementSource(videoPlayer);
        audioSource.connect(mainGainNode);
    } catch (err) {
        console.warn("Failed to initialize Web Audio API, falling back to native media volume controls:", err);
        useWebAudio = false;
        audioCtx = null;
        mainGainNode = null;
        analyser = null;
        audioSource = null;
    }
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

function play() {
    if (timeline.length === 0) return;
    isPlaying = true;
    playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    viewportStatus.textContent = 'Playing';
    
    lastTime = Date.now();
    animationFrameId = requestAnimationFrame(loop);
    
    // Play video element natively once on state change
    const item = timeline[activeTimelineIndex];
    if (item) {
        videoPlayer.muted = (useWebAudio) ? false : isMuted;
        if (videoPlayer.paused) {
            videoPlayer.play().catch(err => console.log('Playback deferred:', err));
        }
    }
}

function pause() {
    isPlaying = false;
    playBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
    viewportStatus.textContent = 'Paused';
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    
    if (!videoPlayer.paused) {
        videoPlayer.pause();
    }
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
    syncVolumeAndFade();
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

function skipBackward() {
    seekTo(currentGlobalTime - 15.0);
}

function skipForward() {
    seekTo(currentGlobalTime + 15.0);
}

// Seek Timeline
function seekTo(globalTime) {
    currentGlobalTime = Math.max(0, Math.min(totalDuration, globalTime));
    
    const oldIndex = activeTimelineIndex;
    updateTimelineState();
    
    // If the segment index did not change, seek the active player to new local position
    if (oldIndex === activeTimelineIndex) {
        const item = timeline[activeTimelineIndex];
        if (item) {
            if (item.type === 'video') {
                const localTime = currentGlobalTime - item.startGlobal;
                const clipInfo = plan.find(c => c.num === item.clipNum);
                const isAudioOnly = clipInfo && clipInfo.audio_only === true;
                const playOffset = (currentMode === 'audio' && !isAudioOnly) ? 2.0 : 0.0;
                videoPlayer.currentTime = localTime + playOffset;
            } else if (item.type === 'bridge') {
                const elapsed = currentGlobalTime - item.startGlobal;
                const prevVideoItem = activeTimelineIndex > 0 ? timeline[activeTimelineIndex - 1] : null;
                if (prevVideoItem) {
                    const baseDur = prevVideoItem.duration;
                    videoPlayer.currentTime = Math.max(0, baseDur - 5.0) + elapsed;
                }
            }
        }
    }
    
    syncVolumeAndFade();
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
        const localTime = currentGlobalTime - item.startGlobal;
        const clipInfo = plan.find(c => c.num === item.clipNum);
        const isAudioOnly = clipInfo && clipInfo.audio_only === true;
        const playOffset = (currentMode === 'audio' && !isAudioOnly) ? 2.0 : 0.0;
        
        if (videoPlayer.getAttribute('data-src') !== item.src) {
            videoPlayer.onloadedmetadata = null;
            videoPlayer.setAttribute('data-src', item.src);
            videoPlayer.src = item.src;
            videoPlayer.load();
            
            videoPlayer.onloadedmetadata = () => {
                videoPlayer.currentTime = localTime + playOffset;
                if (isPlaying) {
                    videoPlayer.muted = (useWebAudio) ? false : isMuted;
                    videoPlayer.play().catch(() => {});
                }
            };
        } else {
            videoPlayer.currentTime = localTime + playOffset;
            if (isPlaying && videoPlayer.paused) {
                videoPlayer.muted = (useWebAudio) ? false : isMuted;
                videoPlayer.play().catch(() => {});
            }
        }
    } else if (item.type === 'bridge') {
        const elapsed = currentGlobalTime - item.startGlobal;
        const prevVideoItem = activeTimelineIndex > 0 ? timeline[activeTimelineIndex - 1] : null;
        
        if (prevVideoItem) {
            const baseDur = prevVideoItem.duration;
            videoPlayer.currentTime = Math.max(0, baseDur - 5.0) + elapsed;
            if (isPlaying && videoPlayer.paused) {
                videoPlayer.muted = (useWebAudio) ? false : isMuted;
                videoPlayer.play().catch(() => {});
            }
        }
    }
}

// Keep volume nodes synced and handle crossfades/fades
function syncVolumeAndFade() {
    const item = timeline[activeTimelineIndex];
    if (!item) return;
    
    let fade = 1.0;
    
    if (item.type === 'video') {
        const localTime = currentGlobalTime - item.startGlobal;
        const clipInfo = plan.find(c => c.num === item.clipNum);
        const crossfadeDuration = (clipInfo && clipInfo.crossfade !== undefined) ? clipInfo.crossfade : 0.0;
        
        if (crossfadeDuration > 0) {
            if (localTime < crossfadeDuration) {
                fade = localTime / crossfadeDuration;
            } else if (localTime > item.duration - crossfadeDuration) {
                fade = (item.duration - localTime) / crossfadeDuration;
            }
        }
    } else if (item.type === 'bridge') {
        const elapsed = currentGlobalTime - item.startGlobal;
        fade = Math.max(0, Math.min(1, 1.0 - (elapsed / 5.0)));
    }
    
    fade = Math.max(0, Math.min(1, fade));
    const targetVolume = isMuted ? 0.0 : currentVolume * fade;
    
    if (useWebAudio && mainGainNode && audioCtx) {
        mainGainNode.gain.value = targetVolume;
    } else {
        videoPlayer.volume = targetVolume;
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
        if (useWebAudio && mainGainNode && audioCtx) {
            mainGainNode.gain.value = 0.0;
        } else {
            videoPlayer.muted = true;
        }
    } else {
        muteBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
        if (useWebAudio && mainGainNode && audioCtx) {
            videoPlayer.muted = false;
            mainGainNode.gain.value = currentVolume;
        } else {
            videoPlayer.muted = false;
            videoPlayer.volume = currentVolume;
        }
    }
}

function setVolume(val) {
    initAudio();
    currentVolume = Math.max(0, Math.min(1, val));
    volumeSlider.value = currentVolume;
    
    if (useWebAudio && !isMuted && mainGainNode && audioCtx) {
        mainGainNode.gain.value = currentVolume;
    } else if (!useWebAudio) {
        videoPlayer.volume = currentVolume;
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
            const clipInfo = plan.find(c => c.num === item.clipNum);
            if (clipInfo && clipInfo.audio_only) {
                ctx.fillStyle = '#000000';
                ctx.fillRect(0, 0, viewport.width, viewport.height);
            } else {
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
    
    const titleSize = Math.max(22, Math.floor(viewport.width * 0.045));
    ctx.font = `800 ${titleSize}px Outfit`;
    ctx.fillText("Editor's Preview", viewport.width / 2, viewport.height / 2 - 25);
    
    const subtitleSize = Math.max(14, Math.floor(viewport.width * 0.025));
    ctx.font = `400 ${subtitleSize}px Outfit`;
    ctx.fillStyle = '#8c9bb0';
    ctx.fillText('Click play to preview compiled timeline segments', viewport.width / 2, viewport.height / 2 + 25);
}

function drawBridgeSlide(text) {
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    
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
    const gradient = ctx.createRadialGradient(viewport.width/2, viewport.height/2, 50, viewport.width/2, viewport.height/2, viewport.width/2);
    gradient.addColorStop(0, '#111424');
    gradient.addColorStop(1, '#07090e');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    
    ctx.fillStyle = '#f1f3f9';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    // Top header (relative font size and position)
    const headerFontSize = Math.max(16, Math.floor(viewport.width * 0.035));
    ctx.font = `800 ${headerFontSize}px Outfit`;
    ctx.fillText('🎧 AUDIO PREVIEW MODE', viewport.width / 2, viewport.height * 0.15);
    
    // Middle title (wrapped, relative position)
    const titleFontSize = Math.max(18, Math.floor(viewport.width * 0.04));
    ctx.font = `600 ${titleFontSize}px Outfit`;
    ctx.fillStyle = '#a29bfe';
    
    const titleText = `Clip ${item.clipNum}: ${item.title}`;
    const titleLines = wrapText(ctx, titleText, viewport.width - 60);
    const titleLineHeight = titleFontSize + 8;
    const titleStartY = (viewport.height * 0.38) - ((titleLines.length - 1) * titleLineHeight / 2);
    
    titleLines.forEach((line, idx) => {
        ctx.fillText(line, viewport.width / 2, titleStartY + (idx * titleLineHeight));
    });
    
    const centerY = viewport.height * 0.6;
    if (analyser && isPlaying) {
        analyser.getByteTimeDomainData(dataArray);
        
        ctx.lineWidth = 4;
        ctx.strokeStyle = 'rgba(162, 155, 254, 0.85)';
        ctx.shadowColor = '#6c5ce7';
        ctx.shadowBlur = 20;
        
        ctx.beginPath();
        const sliceWidth = viewport.width / bufferLength;
        let x = 0;
        
        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = (v - 1.0) * (viewport.height * 0.2) + centerY;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
            x += sliceWidth;
        }
        
        ctx.lineTo(viewport.width, centerY);
        ctx.stroke();
        ctx.shadowBlur = 0;
        
        analyser.getByteFrequencyData(dataArray);
        const barWidth = (viewport.width / bufferLength) * 1.5;
        let barX = 0;
        ctx.fillStyle = 'rgba(108, 92, 231, 0.12)';
        
        const maxBarHeight = viewport.height * 0.15;
        for (let i = 0; i < bufferLength; i++) {
            const barHeight = (dataArray[i] / 255.0) * maxBarHeight;
            ctx.fillRect(barX, viewport.height - barHeight - 20, barWidth - 2, barHeight);
            barX += barWidth;
        }
    } else {
        const statusFontSize = Math.max(14, Math.floor(viewport.width * 0.028));
        ctx.font = `500 ${statusFontSize}px Outfit`;
        ctx.fillStyle = '#636e72';
        ctx.fillText(isPlaying ? 'Initializing visualizer...' : 'Press Play to start visualizer', viewport.width / 2, viewport.height * 0.78);
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
