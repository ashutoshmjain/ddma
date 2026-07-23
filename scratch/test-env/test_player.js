const puppeteer = require('puppeteer');

async function runTest() {
    console.log("🚀 Starting Headless Browser Player Test...");
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--autoplay-policy=no-user-gesture-required',
            '--mute-audio',
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ]
    });
    const page = await browser.newPage();

    // Capture console logs inside the page
    page.on('console', msg => {
        console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
    });

    page.on('pageerror', err => {
        console.error(`[Browser Page Error] ${err.toString()}`);
    });

    // Log request failures to see what 404s
    page.on('response', response => {
        if (response.status() >= 400) {
            console.log(`[Browser Network Error] ${response.url()} returned status ${response.status()}`);
        }
    });

    try {
        console.log("Navigating to http://127.0.0.1:8000/docs/index.html ...");
        await page.goto('http://127.0.0.1:8000/docs/index.html', { waitUntil: 'networkidle2' });

        // Wait 4 seconds for plan.json to load and video duration probing to finish
        console.log("Waiting for durations probing...");
        await new Promise(r => setTimeout(r, 4500));

        // Evaluate baseline state from DOM
        const state = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const clipCards = document.querySelectorAll('.clip-item');
            const totalTimeTxt = document.getElementById('totalTimeLabel').textContent;
            const statusTxt = document.getElementById('viewportStatus').textContent;
            return {
                totalTimeText: totalTimeTxt,
                clipsCount: clipCards.length,
                videoSrc: videoEl ? videoEl.src : null,
                videoMuted: videoEl ? videoEl.muted : null,
                videoPaused: videoEl ? videoEl.paused : null,
                statusText: statusTxt
            };
        });

        console.log("\n📊 Baseline State Checklist:");
        console.log(`- Timeline Total Duration Label: ${state.totalTimeText}`);
        console.log(`- Sidebar Clip Cards Rendered: ${state.clipsCount}`);
        console.log(`- Video Element Source: ${state.videoSrc}`);
        console.log(`- Video Element Muted: ${state.videoMuted}`);
        console.log(`- Video Element Paused: ${state.videoPaused}`);
        console.log(`- Viewport Status text: ${state.statusText}`);

        if (state.clipsCount === 0) {
            throw new Error("FAIL: Sidebar clips were not rendered!");
        }
        if (state.totalTimeText === "0:00" || state.totalTimeText === "") {
            throw new Error("FAIL: Total duration label was not populated!");
        }

        // Test Action 1: Click Play
        console.log("\n▶️ Clicking Play Button (#playBtn)...");
        await page.click('#playBtn');
        
        // Wait 3 seconds to let playhead advance
        await new Promise(r => setTimeout(r, 3000));

        const playState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const currentTimeTxt = document.getElementById('currentTimeLabel').textContent;
            const statusTxt = document.getElementById('viewportStatus').textContent;
            return {
                videoPaused: videoEl ? videoEl.paused : null,
                videoMuted: videoEl ? videoEl.muted : null,
                videoVolume: videoEl ? videoEl.volume : null,
                videoCurrentTime: videoEl ? videoEl.currentTime : null,
                currentTimeText: currentTimeTxt,
                statusText: statusTxt
            };
        });

        console.log("\n🔍 Post-Play Playback Check:");
        console.log(`- Viewport Status: ${playState.statusText}`);
        console.log(`- Video Paused: ${playState.videoPaused}`);
        console.log(`- Video Muted: ${playState.videoMuted}`);
        console.log(`- Video Volume: ${playState.videoVolume}`);
        console.log(`- Video currentTime: ${playState.videoCurrentTime}s`);
        console.log(`- Current Time Label: ${playState.currentTimeText}`);

        if (playState.statusText !== 'Playing') {
            throw new Error("FAIL: Viewport status text did not toggle to 'Playing'!");
        }
        if (playState.videoPaused) {
            throw new Error("FAIL: Video element is still paused after clicking play!");
        }
        if (playState.videoCurrentTime <= 0.05) {
            throw new Error(`FAIL: Video playhead did not advance! Current time: ${playState.videoCurrentTime}`);
        }

        // Test Action 1b: Test Skip Buttons (Forward/Backward 15s)
        console.log("\n⏩ Clicking Skip Forward Button (#skipForwardBtn)...");
        const prevTime = playState.videoCurrentTime;
        await page.click('#skipForwardBtn');
        await new Promise(r => setTimeout(r, 1000));

        const skipForwardState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                videoCurrentTime: videoEl ? videoEl.currentTime : null
            };
        });
        console.log(`- Video currentTime after skip forward: ${skipForwardState.videoCurrentTime}s (was ${prevTime}s)`);
        
        if (skipForwardState.videoCurrentTime < prevTime + 13.0) {
            throw new Error(`FAIL: Video playhead did not skip forward by ~15s! Target was ~${prevTime + 15}s, got ${skipForwardState.videoCurrentTime}s`);
        }

        console.log("\n⏪ Clicking Skip Backward Button (#skipBackBtn)...");
        await page.click('#skipBackBtn');
        await new Promise(r => setTimeout(r, 1000));

        const skipBackState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                videoCurrentTime: videoEl ? videoEl.currentTime : null
            };
        });
        console.log(`- Video currentTime after skip backward: ${skipBackState.videoCurrentTime}s`);
        
        if (skipBackState.videoCurrentTime > skipForwardState.videoCurrentTime - 12.0) {
            throw new Error(`FAIL: Video playhead did not skip backward by ~15s! Target was ~${skipForwardState.videoCurrentTime - 15}s, got ${skipBackState.videoCurrentTime}s`);
        }

        // Test Action 2: Click Mute
        console.log("\n🔇 Clicking Mute Button (#muteBtn)...");
        await page.click('#muteBtn');
        await new Promise(r => setTimeout(r, 500));

        const muteState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                videoMuted: videoEl ? videoEl.muted : null,
                videoVolume: videoEl ? videoEl.volume : null
            };
        });

        console.log("🔍 Post-Mute Check:");
        console.log(`- Video Element Muted: ${muteState.videoMuted}`);
        console.log(`- Video Element Volume: ${muteState.videoVolume}`);

        if (!muteState.videoMuted) {
            throw new Error("FAIL: Video element is not muted!");
        }

        // Test Action 3: Click Unmute
        console.log("\n🔊 Clicking Mute Button again to Unmute...");
        await page.click('#muteBtn');
        await new Promise(r => setTimeout(r, 500));

        const unmuteState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return {
                videoMuted: videoEl ? videoEl.muted : null,
                videoVolume: videoEl ? videoEl.volume : null
            };
        });

        console.log("🔍 Post-Unmute Check:");
        console.log(`- Video Element Muted: ${unmuteState.videoMuted}`);
        console.log(`- Video Element Volume: ${unmuteState.videoVolume}`);

        if (unmuteState.videoMuted) {
            throw new Error("FAIL: Video element remained muted after toggle!");
        }
        if (unmuteState.videoVolume === 0) {
            throw new Error("FAIL: Video volume is zero after unmute!");
        }

        // Test Action 4: Click Pause
        console.log("\n⏸️ Clicking Play Button to Pause...");
        await page.click('#playBtn');
        await new Promise(r => setTimeout(r, 1000));

        const pauseState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const statusTxt = document.getElementById('viewportStatus').textContent;
            return {
                videoPaused: videoEl ? videoEl.paused : null,
                videoCurrentTime: videoEl ? videoEl.currentTime : null,
                statusText: statusTxt
            };
        });

        console.log("🔍 Post-Pause Check:");
        console.log(`- Viewport Status: ${pauseState.statusText}`);
        console.log(`- Video Paused: ${pauseState.videoPaused}`);
        console.log(`- Video Playhead Position: ${pauseState.videoCurrentTime}s`);

        if (pauseState.statusText !== 'Paused') {
            throw new Error("FAIL: Viewport status text did not toggle back to 'Paused'!");
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
