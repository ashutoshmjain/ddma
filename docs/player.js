// Player State
let plan = [];
let timeline = [];
let currentGlobalTime = 0; // seconds
let totalDuration = 0;
let isPlaying = false;
let animationFrameId = null;
let activeTimelineIndex = -1;
let currentMode = 'video'; // 'video' or 'audio'

// Audio Graph
let audioCtx = null;
let videoSources = []; // MediaElementAudioSourceNode mappings
let mainGainNode = null;
let currentVolume = 0.8;
let analyser = null;
let dataArray = null;
let bufferLength = 0;
let gainNode1 = null;
let gainNode2 = null;

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

    // Filter plan based on active mode
    const filteredPlan = plan.filter(clip => {
        // Both modes only play locked and unhidden clips
        if (!clip.locked || clip.hidden) {
            return false;
        }
        // Video Mode also filters out audio-only clips
        if (currentMode === 'video' && clip.audio_only) {
            return false;
        }
        return true;
    });

    filteredPlan.forEach((clip, index) => {
        // 1. Add Bridge Card if it is not the first clip (skip in audio mode)
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

        // 2. Add Video Clip
        const isAudioOnly = clip.audio_only === true;
        const clipSrc = isAudioOnly 
            ? `/previews/preview_episode_244_${clip.num}.mp3`
            : `/docs/assets/clips/244-${clip.num}.mp4`;

        timeline.push({
            type: 'video',
            clipNum: clip.num,
            title: clip.title,
            duration: 10.0, // Default fallback, updated later
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

// Load Video Durations Dynamically
async function loadVideoDurations() {
    let runningTime = 0;
    const validatedTimeline = [];

    for (let i = 0; i < timeline.length; i++) {
        const item = timeline[i];
        if (item.type === 'video') {
            try {
                let duration = await getVideoDuration(item.src);
                const clipInfo = plan.find(c => c.num === item.clipNum);
                
                // Fallback if NaN or invalid duration probed
                if (isNaN(duration) || duration <= 0) {
                    const baseDur = calculateClipDuration(clipInfo);
                    duration = baseDur + (currentMode === 'audio' ? 0.0 : 2.0);
                } else {
                    // Subtract 2.0s title card intro from video clips in audio preview mode
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
                console.warn(`Could not probe duration for ${item.src}, trying fallback...`, err);
                const clipInfo = plan.find(c => c.num === item.clipNum);
                
                if (currentMode === 'video') {
                    // In Video Mode, exclude if the asset file is missing
                    console.warn(`Excluding missing video asset: ${item.src}`);
                    if (validatedTimeline.length > 0 && validatedTimeline[validatedTimeline.length - 1].type === 'bridge' && validatedTimeline[validatedTimeline.length - 1].clipNum === item.clipNum) {
                        validatedTimeline.pop();
                    }
                } else {
                    // In Audio Mode, fall back to calculated duration from plan segments
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
    renderSidebar(); // Re-render with verified clips only
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
        
        tempVideo.load(); // Force loading of metadata to resolve promise
    });
}

// Render Clips in Sidebar
function renderSidebar() {
    clipsList.innerHTML = '';
    
    plan.forEach(clip => {
        // Find corresponding video item in timeline to show its actual duration
        const videoItem = timeline.find(item => item.type === 'video' && item.clipNum === clip.num);
        if (!videoItem) return; // Skip clips that have no compiled video asset
        
        const durationStr = formatTime(videoItem.duration);
        
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
    
    // Wire up AnalyserNode for audio mode visualizer
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    bufferLength = analyser.frequencyBinCount;
    dataArray = new Uint8Array(bufferLength);
    
    mainGainNode.connect(analyser);
    analyser.connect(audioCtx.destination);
    
    // Create individual gain nodes for crossfading
    gainNode1 = audioCtx.createGain();
    gainNode2 = audioCtx.createGain();
    gainNode1.connect(mainGainNode);
    gainNode2.connect(mainGainNode);
    
    // Connect our video tags to the audio context
    videoPlayer1.muted = false;
    videoPlayer2.muted = false;
    setupVideoAudioNode(videoPlayer1, gainNode1);
    setupVideoAudioNode(videoPlayer2, gainNode2);
}

function setupVideoAudioNode(videoEl, gainNode) {
    const source = audioCtx.createMediaElementSource(videoEl);
    source.connect(gainNode);
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

function safeSetTimeAndPlay(videoEl, time) {
    const playVideo = () => {
        try {
            if (Math.abs(videoEl.currentTime - time) > 0.3) {
                videoEl.currentTime = time;
            }
        } catch (e) {
            console.warn("Failed to set currentTime:", e);
        }
        
        if (isPlaying) {
            videoEl.muted = false; // Bypass browser-level mute resets on load()
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
    
    // Load Video Source in buffer
    if (item.type === 'video') {
        const localTime = currentGlobalTime - item.startGlobal;
        
        // Check if source matches inactive player (which has preloaded it)        // Swap players!
        if (inactiveVideoPlayer.getAttribute('data-src') === item.src) {
            const temp = activeVideoPlayer;
            activeVideoPlayer = inactiveVideoPlayer;
            inactiveVideoPlayer = temp;
        } else if (activeVideoPlayer.getAttribute('data-src') !== item.src) {
            activeVideoPlayer.setAttribute('data-src', item.src);
            activeVideoPlayer.src = item.src;
            activeVideoPlayer.load();
        }
        
        const clipInfo = plan.find(c => c.num === item.clipNum);
        const isAudioOnly = clipInfo && clipInfo.audio_only === true;
        const playOffset = (currentMode === 'audio' && !isAudioOnly) ? 2.0 : 0.0;
        
        safeSetTimeAndPlay(activeVideoPlayer, localTime + playOffset);
        
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
                
                try {
                    activeVideoPlayer.currentTime = prevVideoItem.duration + elapsedSinceVideoEnd;
                } catch (e) {}
                
                if (isPlaying) {
                    activeVideoPlayer.play().catch(() => {});
                }
                
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

// Keep physical HTML5 video nodes synchronized and handle crossfades
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
        
        let activeFade = 1.0;
        let inactiveFade = 0.0;
        
        if (crossfadeDuration > 0) {
            if (localTime < crossfadeDuration) {
                // Fade-in region for active player
                activeFade = localTime / crossfadeDuration;
                // Fade-out region for inactive player (fading out preceding clip)
                inactiveFade = 1.0 - (localTime / crossfadeDuration);
            } else if (localTime > item.duration - crossfadeDuration) {
                // Fade-out region at the end of the active player
                inactiveFade = 0.0;
                activeFade = (item.duration - localTime) / crossfadeDuration;
            }
        }
        
        activeFade = Math.max(0, Math.min(1, activeFade));
        inactiveFade = Math.max(0, Math.min(1, inactiveFade));
        
        // Apply gains to the respective player's GainNode
        if (gainNode1 && gainNode2) {
            const activeGainNode = getGainNodeForPlayer(activeVideoPlayer);
            const inactiveGainNode = getGainNodeForPlayer(inactiveVideoPlayer);
            
            activeGainNode.gain.setValueAtTime(activeFade, audioCtx.currentTime);
            inactiveGainNode.gain.setValueAtTime(inactiveFade, audioCtx.currentTime);
        }
        
        const isAudioOnly = clipInfo && clipInfo.audio_only === true;
        const playOffset = (currentMode === 'audio' && !isAudioOnly) ? 2.0 : 0.0;
        
        safeSetTimeAndPlay(activeVideoPlayer, localTime + playOffset);
        
        // Control playback of inactive player during crossfade
        if (inactiveFade > 0 && isPlaying) {
            inactiveVideoPlayer.muted = false; // Bypass browser-level mute resets on load()
            if (inactiveVideoPlayer.paused) {
                inactiveVideoPlayer.play().catch(() => {});
            }
        } else {
            if (!inactiveVideoPlayer.paused) {
                inactiveVideoPlayer.pause();
            }
            // Only preload next video once crossfade has finished
            preloadNextVideo();
        }
    } else if (item.type === 'bridge') {
        if (gainNode1 && gainNode2) {
            // Bridge card: active player fades out (preceding clip tail)
            const activeGainNode = getGainNodeForPlayer(activeVideoPlayer);
            
            // Bridge fade: linearly fade preceding clip out over the 5-second bridge card
            const elapsed = currentGlobalTime - item.startGlobal;
            const fade = Math.max(0, Math.min(1, 1.0 - (elapsed / 5.0)));
            
            activeGainNode.gain.setValueAtTime(fade, audioCtx.currentTime);
            
            const inactiveGainNode = getGainNodeForPlayer(inactiveVideoPlayer);
            inactiveGainNode.gain.setValueAtTime(0.0, audioCtx.currentTime);
        }
        
        if (!inactiveVideoPlayer.paused) {
            inactiveVideoPlayer.pause();
        }
        
        if (isPlaying) {
            activeVideoPlayer.muted = false; // Bypass browser-level mute resets on load()
            if (activeVideoPlayer.paused) {
                activeVideoPlayer.play().catch(() => {});
            }
        } else {
            if (!activeVideoPlayer.paused) {
                activeVideoPlayer.pause();
            }
        }
    }
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

function getGainNodeForPlayer(videoEl) {
    return videoEl === videoPlayer1 ? gainNode1 : gainNode2;
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
                ctx.drawImage(activeVideoPlayer, 0, 0, viewport.width, viewport.height);
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
            // Draw a smooth wave in the center region
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
        // Fallback static wave line if audio context is not active/paused
        ctx.lineWidth = 3;
        ctx.strokeStyle = 'rgba(162, 155, 254, 0.3)';
        ctx.beginPath();
        ctx.moveTo(0, viewport.height / 2 + 20);
        ctx.lineTo(viewport.width, viewport.height / 2 + 20);
        ctx.stroke();
        
        ctx.font = '300 16px Outfit';
        ctx.fillStyle = '#8c9bb0';
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
