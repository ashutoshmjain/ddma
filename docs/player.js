// Player State
let plan = [];
let timeline = [];
let currentGlobalTime = 0; // seconds
let totalDuration = 0;
let isPlaying = false;
let animationFrameId = null;
let activeTimelineIndex = -1;

// Audio Graph
let audioCtx = null;
let videoSources = []; // MediaElementAudioSourceNode mappings
let mainGainNode = null;
let currentVolume = 0.8;

// UI Elements
const viewport = document.getElementById('viewport');
const ctx = viewport.getContext('2d');
const playBtn = document.getElementById('playBtn');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const muteBtn = document.getElementById('muteBtn');
const volumeSlider = document.getElementById('volumeSlider');
const seekTrack = document.getElementById('seekTrack');
const seekProgress = document.getElementById('seekProgress');
const seekHandle = document.getElementById('seekHandle');
const currentTimeLabel = document.getElementById('currentTimeLabel');
const totalTimeLabel = document.getElementById('totalTimeLabel');
const clipsList = document.getElementById('clipsList');
const viewportStatus = document.getElementById('viewportStatus');

// Double buffer video players
const videoPlayer1 = document.getElementById('videoPlayer1');
const videoPlayer2 = document.getElementById('videoPlayer2');
let activeVideoPlayer = videoPlayer1;
let inactiveVideoPlayer = videoPlayer2;

// Initialize
window.addEventListener('DOMContentLoaded', async () => {
    try {
        await loadPlan();
        initUI();
    } catch (err) {
        console.error('Initialization failed:', err);
        clipsList.innerHTML = `<div class="loading-placeholder"><i class="fa-solid fa-triangle-exclamation" style="color: #ff7675;"></i><span>Failed to load plan.json</span></div>`;
    }
});

// Load plan.json
async function loadPlan() {
    const res = await fetch('plan.json');
    if (!res.ok) throw new Error('Could not fetch plan.json');
    plan = await res.json();
    
    // Build initial timeline of items (We assume default video durations of 10s until metadata loads)
    buildTimeline();
    renderSidebar();
    
    // Bootstrap video player metadata load
    await loadVideoDurations();
}

// Build timeline structure: Video Clip -> Bridge Slide -> Video Clip
function buildTimeline() {
    timeline = [];
    let runningTime = 0;

    plan.forEach((clip, index) => {
        // 1. Add Bridge Card if it is not the first clip
        if (index > 0 && clip.bridge_text && clip.bridge_text.length > 0) {
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

        // 2. Add Video Clip
        timeline.push({
            type: 'video',
            clipNum: clip.num,
            title: clip.title,
            duration: 10.0, // Default fallback, updated later
            startGlobal: runningTime,
            endGlobal: runningTime + 10.0,
            src: `assets/clips/244-${clip.num}.mp4`
        });
        runningTime += 10.0;
    });

    updateTotalDuration();
}

function updateTotalDuration() {
    totalDuration = timeline.length > 0 ? timeline[timeline.length - 1].endGlobal : 0;
    totalTimeLabel.textContent = formatTime(totalDuration);
}

// Load Video Durations Dynamically
async function loadVideoDurations() {
    let runningTime = 0;

    for (let i = 0; i < timeline.length; i++) {
        const item = timeline[i];
        if (item.type === 'video') {
            item.startGlobal = runningTime;
            
            // Query duration by pre-loading video metadata
            try {
                const duration = await getVideoDuration(item.src);
                item.duration = duration;
            } catch (err) {
                console.warn(`Could not load duration for ${item.src}, using default 10s.`, err);
                item.duration = 15.0; // standard clip fallback
            }
            
            item.endGlobal = runningTime + item.duration;
            runningTime += item.duration;
        } else if (item.type === 'bridge') {
            item.startGlobal = runningTime;
            item.endGlobal = runningTime + item.duration;
            runningTime += item.duration;
        }
    }

    updateTotalDuration();
    renderSidebar(); // Re-render with correct times
    seekTo(0); // Reset seeker
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
    });
}

// Render Clips in Sidebar
function renderSidebar() {
    clipsList.innerHTML = '';
    
    plan.forEach(clip => {
        // Find corresponding video item in timeline to show its actual duration
        const videoItem = timeline.find(item => item.type === 'video' && item.clipNum === clip.num);
        const durationStr = videoItem ? formatTime(videoItem.duration) : '--:--';
        
        const card = document.createElement('div');
        card.className = `clip-item`;
        card.id = `sidebar-clip-${clip.num}`;
        card.innerHTML = `
            <div class="clip-item-row1">
                <span>CLIP ${clip.num}</span>
                <span class="clip-duration">${durationStr}</span>
            </div>
            <div class="clip-meta-title">${clip.title}</div>
        `;
        
        card.onclick = () => {
            if (videoItem) {
                seekTo(videoItem.startGlobal);
            }
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
function initUI() {
    playBtn.addEventListener('click', togglePlay);
    prevBtn.addEventListener('click', playPrevious);
    nextBtn.addEventListener('click', playNext);
    
    volumeSlider.addEventListener('input', (e) => {
        setVolume(parseFloat(e.target.value));
    });
    
    muteBtn.addEventListener('click', toggleMute);
    
    // Seek tracking controls
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

    // Resize viewport to keep square aspect ratio crisp
    window.addEventListener('resize', drawFrame);
    
    // Initial paint
    drawFrame();
}

function handleSeekEvent(e) {
    const rect = seekTrack.getBoundingClientRect();
    let pos = (e.clientX - rect.left) / rect.width;
    pos = Math.max(0, Math.min(1, pos));
    seekTo(pos * totalDuration);
}

// Web Audio API Setup
function initAudio() {
    if (audioCtx) return;
    
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass();
    
    mainGainNode = audioCtx.createGain();
    mainGainNode.gain.setValueAtTime(currentVolume, audioCtx.currentTime);
    mainGainNode.connect(audioCtx.destination);
    
    // Connect our video tags to the audio context
    setupVideoAudioNode(videoPlayer1);
    setupVideoAudioNode(videoPlayer2);
}

function setupVideoAudioNode(videoEl) {
    const source = audioCtx.createMediaElementSource(videoEl);
    source.connect(mainGainNode);
    videoSources.push(source);
}

// Toggle Play / Pause
function togglePlay() {
    initAudio();
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    
    if (isPlaying) {
        pause();
    } else {
        play();
    }
}

function play() {
    isPlaying = true;
    playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    viewportStatus.textContent = 'Playing Episode';
    
    // Start playback loop
    let lastTime = performance.now();
    
    function loop(now) {
        if (!isPlaying) return;
        
        const delta = (now - lastTime) / 1000;
        lastTime = now;
        
        currentGlobalTime += delta;
        if (currentGlobalTime >= totalDuration) {
            currentGlobalTime = totalDuration;
            pause();
            seekTo(0);
            return;
        }
        
        updateTimelineState();
        updateSeekUI();
        drawFrame();
        
        animationFrameId = requestAnimationFrame(loop);
    }
    
    // Trigger video playback if active element matches
    syncVideoPlayback();
    animationFrameId = requestAnimationFrame(loop);
}

function pause() {
    isPlaying = false;
    playBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
    viewportStatus.textContent = 'Paused';
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    
    videoPlayer1.pause();
    videoPlayer2.pause();
}

function playPrevious() {
    // Go to start of current item, or if close to start, the previous item
    const threshold = 2.0; // seconds
    let activeItem = timeline[activeTimelineIndex];
    
    if (!activeItem) return;
    
    if (currentGlobalTime - activeItem.startGlobal > threshold) {
        seekTo(activeItem.startGlobal);
    } else {
        // Find previous video item
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

// Seek Timeline
function seekTo(globalTime) {
    currentGlobalTime = Math.max(0, Math.min(totalDuration, globalTime));
    updateTimelineState();
    syncVideoPlayback();
    updateSeekUI();
    drawFrame();
}

// Track active item and schedule buffering
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
    
    // Load Video Source in buffer
    if (item.type === 'video') {
        const localTime = currentGlobalTime - item.startGlobal;
        
        // Check if source matches active player
        if (activeVideoPlayer.getAttribute('data-src') !== item.src) {
            activeVideoPlayer.setAttribute('data-src', item.src);
            activeVideoPlayer.src = item.src;
            activeVideoPlayer.load();
        }
        
        activeVideoPlayer.currentTime = localTime;
        
        // Pre-buffer next video clip into inactive player
        preloadNextVideo();
    } else if (item.type === 'bridge') {
        // For bridge transition slides, we draw text.
        // We let the previous clip continue its audio tail (fade-out)
        // Find previous video item
        let prevVideoItem = null;
        for (let i = activeTimelineIndex - 1; i >= 0; i--) {
            if (timeline[i].type === 'video') {
                prevVideoItem = timeline[i];
                break;
            }
        }
        
        if (prevVideoItem) {
            // Keep playing the tail of preceding video, but mute it or fade it out
            if (activeVideoPlayer.getAttribute('data-src') === prevVideoItem.src) {
                // Keep playing past its end for bridge audio overlay
                const elapsedSinceVideoEnd = currentGlobalTime - prevVideoItem.endGlobal;
                activeVideoPlayer.currentTime = prevVideoItem.duration + elapsedSinceVideoEnd;
                
                // Volume fade out effect in code
                if (mainGainNode) {
                    const fadeRatio = Math.max(0, 1 - (elapsedSinceVideoEnd / 5.0)); // 5s linear fade
                    mainGainNode.gain.setValueAtTime(currentVolume * fadeRatio, audioCtx.currentTime);
                }
            }
        }
    }
}

function preloadNextVideo() {
    let nextVideoItem = null;
    for (let i = activeTimelineIndex + 1; i < timeline.length; i++) {
        if (timeline[i].type === 'video') {
            nextVideoItem = timeline[i];
            break;
        }
    }
    
    if (nextVideoItem && inactiveVideoPlayer.getAttribute('data-src') !== nextVideoItem.src) {
        inactiveVideoPlayer.setAttribute('data-src', nextVideoItem.src);
        inactiveVideoPlayer.src = nextVideoItem.src;
        inactiveVideoPlayer.preload = 'auto';
        inactiveVideoPlayer.load();
    }
}

// Keep physical HTML5 video nodes synchronized
function syncVideoPlayback() {
    const item = timeline[activeTimelineIndex];
    if (!item) return;
    
    if (item.type === 'video') {
        const localTime = currentGlobalTime - item.startGlobal;
        activeVideoPlayer.currentTime = localTime;
        
        // Restore volume node
        if (mainGainNode && audioCtx) {
            mainGainNode.gain.setValueAtTime(currentVolume, audioCtx.currentTime);
        }
        
        if (isPlaying) {
            activeVideoPlayer.play().catch(err => console.log('Autoplay deferred:', err));
        } else {
            activeVideoPlayer.pause();
        }
        inactiveVideoPlayer.pause();
    } else if (item.type === 'bridge') {
        // Bridge slide: Inactive player pauses
        inactiveVideoPlayer.pause();
        
        // Keep playing preceding video elements tail if applicable
        if (isPlaying) {
            activeVideoPlayer.play().catch(() => {});
        } else {
            activeVideoPlayer.pause();
        }
    }
}

// Update Seeker Progress UI
function updateSeekUI() {
    const percent = totalDuration > 0 ? (currentGlobalTime / totalDuration) * 100 : 0;
    seekProgress.style.width = `${percent}%`;
    seekHandle.style.left = `${percent}%`;
    currentTimeLabel.textContent = formatTime(currentGlobalTime);
}

// Volume Controls
function setVolume(val) {
    currentVolume = val;
    volumeSlider.value = val;
    
    if (mainGainNode && audioCtx) {
        mainGainNode.gain.setValueAtTime(val, audioCtx.currentTime);
    }
    
    if (val === 0) {
        muteBtn.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
    } else if (val < 0.5) {
        muteBtn.innerHTML = '<i class="fa-solid fa-volume-low"></i>';
    } else {
        muteBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    }
}

function toggleMute() {
    if (currentVolume > 0) {
        setVolume(0);
    } else {
        setVolume(0.8);
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
    
    if (item.type === 'video') {
        // Paint active video frame onto Canvas
        ctx.drawImage(activeVideoPlayer, 0, 0, viewport.width, viewport.height);
    } else if (item.type === 'bridge') {
        drawBridgeSlide(item.text);
    }
}

function drawIntroScreen() {
    ctx.fillStyle = '#f1f3f9';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    ctx.font = '800 32px Outfit';
    ctx.fillText('DDMA Dynamic Web Player', viewport.width / 2, viewport.height / 2 - 20);
    
    ctx.font = '400 18px Outfit';
    ctx.fillStyle = '#8c9bb0';
    ctx.fillText('Click play to compile and run episode 244', viewport.width / 2, viewport.height / 2 + 20);
}

function drawBridgeSlide(text) {
    // Black background
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, viewport.width, viewport.height);
    
    // Draw bridge card text
    ctx.fillStyle = '#FFFFFF';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = 'bold 32px "Segoe UI"';
    
    // Wrap text within the Instagram safe zone (padding 60px)
    const maxWidth = viewport.width - 120;
    const lineHeight = 46;
    const x = viewport.width / 2;
    
    const lines = wrapText(ctx, text, maxWidth);
    const startY = (viewport.height / 2) - ((lines.length - 1) * lineHeight / 2);
    
    lines.forEach((line, index) => {
        ctx.fillText(line, x, startY + (index * lineHeight));
    });
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
