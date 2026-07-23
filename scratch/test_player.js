const puppeteer = require('puppeteer');

async function runTest() {
    console.log("🚀 Starting Headless Browser Player Test...");
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio']
    });
    const page = await browser.newPage();

    // Capture console logs inside the page
    const consoleLogs = [];
    page.on('console', msg => {
        const text = msg.text();
        console.log(`[Browser Console] ${msg.type()}: ${text}`);
        consoleLogs.push({ type: msg.type(), text });
    });

    page.on('pageerror', err => {
        console.error(`[Browser Page Error] ${err.toString()}`);
    });

    try {
        console.log("Navigating to player at http://127.0.0.1:8000/docs/index.html ...");
        await page.goto('http://127.0.0.1:8000/docs/index.html', { waitUntil: 'networkidle2' });

        // Wait for page to initialize and populate timeline (at least 3 seconds for metadata fetches)
        console.log("Waiting for player timeline initialization...");
        await new Promise(r => setTimeout(r, 4000));

        // Evaluate baseline state
        const state = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const clipCards = document.querySelectorAll('.clip-item');
            return {
                totalDuration: window.totalDuration,
                timelineLength: window.timeline ? window.timeline.length : 0,
                clipsCount: clipCards.length,
                videoSrc: videoEl ? videoEl.src : null,
                videoMuted: videoEl ? videoEl.muted : null,
                videoPaused: videoEl ? videoEl.paused : null,
                isPlaying: window.isPlaying,
                useWebAudio: window.useWebAudio
            };
        });

        console.log("\n📊 Baseline State Checklist:");
        console.log(`- Timeline Duration: ${state.totalDuration}s`);
        console.log(`- Timeline Segments: ${state.timelineLength}`);
        console.log(`- Sidebar Clip Cards Rendered: ${state.clipsCount}`);
        console.log(`- Video Element Source: ${state.videoSrc}`);
        console.log(`- Video Element Muted: ${state.videoMuted}`);
        console.log(`- Video Element Paused: ${state.videoPaused}`);
        console.log(`- Player isPlaying state: ${state.isPlaying}`);
        console.log(`- useWebAudio state: ${state.useWebAudio}`);

        if (state.timelineLength === 0) {
            throw new Error("FAIL: Timeline was not built successfully! Check fetch plan.json errors.");
        }
        if (state.clipsCount === 0) {
            throw new Error("FAIL: Sidebar clips were not rendered!");
        }

        // Test Action 1: Click Play
        console.log("\n▶️ Clicking Play Button (#playBtn)...");
        await page.click('#playBtn');
        
        // Wait 3 seconds to let playhead advance
        await new Promise(r => setTimeout(r, 3000));

        const playState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                isPlaying: window.isPlaying,
                videoPaused: videoEl ? videoEl.paused : null,
                videoMuted: videoEl ? videoEl.muted : null,
                videoVolume: videoEl ? videoEl.volume : null,
                videoCurrentTime: videoEl ? videoEl.currentTime : null,
                gainValue: (window.mainGainNode) ? window.mainGainNode.gain.value : null
            };
        });

        console.log("\n🔍 Post-Play Playback Check:");
        console.log(`- Player isPlaying: ${playState.isPlaying}`);
        console.log(`- Video Paused: ${playState.videoPaused}`);
        console.log(`- Video Muted: ${playState.videoMuted}`);
        console.log(`- Video Volume: ${playState.videoVolume}`);
        console.log(`- Video currentTime: ${playState.videoCurrentTime}s`);
        console.log(`- Web Audio Gain Node Value: ${playState.gainValue}`);

        if (!playState.isPlaying) {
            throw new Error("FAIL: Player state isPlaying is still false!");
        }
        if (playState.videoPaused) {
            throw new Error("FAIL: Video element is still paused after clicking play!");
        }
        if (playState.videoCurrentTime <= 0.05) {
            throw new Error(`FAIL: Video playhead did not advance! Current time: ${playState.videoCurrentTime}`);
        }
        if (playState.videoMuted && !playState.gainValue) {
            throw new Error("FAIL: Video is muted or silent!");
        }

        // Test Action 2: Click Mute
        console.log("\n🔇 Clicking Mute Button (#muteBtn)...");
        await page.click('#muteBtn');
        await new Promise(r => setTimeout(r, 500));

        const muteState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                isMuted: window.isMuted,
                videoMuted: videoEl ? videoEl.muted : null,
                videoVolume: videoEl ? videoEl.volume : null,
                gainValue: (window.mainGainNode) ? window.mainGainNode.gain.value : null
            };
        });

        console.log("🔍 Post-Mute Check:");
        console.log(`- Player isMuted: ${muteState.isMuted}`);
        console.log(`- Video Element Muted: ${muteState.videoMuted}`);
        console.log(`- Video Element Volume: ${muteState.videoVolume}`);
        console.log(`- Web Audio Gain Value: ${muteState.gainValue}`);

        if (!muteState.isMuted) {
            throw new Error("FAIL: Player state isMuted did not toggle to true!");
        }
        if (muteState.gainValue !== 0 && !muteState.videoMuted) {
            throw new Error("FAIL: Sound channel was not silenced on mute!");
        }

        // Test Action 3: Click Unmute
        console.log("\n🔊 Clicking Mute Button again to Unmute...");
        await page.click('#muteBtn');
        await new Promise(r => setTimeout(r, 500));

        const unmuteState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                isMuted: window.isMuted,
                videoMuted: videoEl ? videoEl.muted : null,
                videoVolume: videoEl ? videoEl.volume : null,
                gainValue: (window.mainGainNode) ? window.mainGainNode.gain.value : null
            };
        });

        console.log("🔍 Post-Unmute Check:");
        console.log(`- Player isMuted: ${unmuteState.isMuted}`);
        console.log(`- Video Element Muted: ${unmuteState.videoMuted}`);
        console.log(`- Video Element Volume: ${unmuteState.videoVolume}`);
        console.log(`- Web Audio Gain Value: ${unmuteState.gainValue}`);

        if (unmuteState.isMuted) {
            throw new Error("FAIL: Player state isMuted did not toggle back to false!");
        }
        if (unmuteState.videoVolume === 0 && unmuteState.gainValue === 0) {
            throw new Error("FAIL: Audio channel remained silent after unmuting!");
        }

        // Test Action 4: Click Pause
        console.log("\n⏸️ Clicking Play Button to Pause...");
        await page.click('#playBtn');
        await new Promise(r => setTimeout(r, 1000));

        const pauseState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                isPlaying: window.isPlaying,
                videoPaused: videoEl ? videoEl.paused : null,
                videoCurrentTime: videoEl ? videoEl.currentTime : null
            };
        });

        console.log("🔍 Post-Pause Check:");
        console.log(`- Player isPlaying: ${pauseState.isPlaying}`);
        console.log(`- Video Paused: ${pauseState.videoPaused}`);
        console.log(`- Video Playhead Position: ${pauseState.videoCurrentTime}s`);

        if (pauseState.isPlaying) {
            throw new Error("FAIL: Player state isPlaying is still true after pausing!");
        }
        if (!pauseState.videoPaused) {
            throw new Error("FAIL: Video element did not pause!");
        }

        console.log("\n✅ ALL END-TO-END E2E TESTS PASSED SUCCESSFULLY!");
    } catch (err) {
        console.error("\n❌ TEST FAILURE DETECTED:");
        console.error(err.message);
        process.exit(1);
    } finally {
        await browser.close();
    }
}

runTest();
