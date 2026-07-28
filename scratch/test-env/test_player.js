const puppeteer = require('puppeteer');

async function runTest() {
    console.log("🚀 Starting Comprehensive Headless Browser Player Regression Suite...");
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

    const capturedErrors = [];

    page.on('console', msg => {
        if (msg.type() === 'error') {
            const text = msg.text();
            if (!text.includes('404') && !text.includes('favicon.ico')) {
                console.log(`[Browser Console ERROR] ${text}`);
                capturedErrors.push(`[Console Error] ${text}`);
            }
        }
    });

    page.on('pageerror', err => {
        console.error(`[Browser Page Exception] ${err.toString()}`);
        capturedErrors.push(`[Page Exception] ${err.toString()}`);
    });

    try {
        console.log("Navigating to http://127.0.0.1:8000/docs/index.html ...");
        await page.goto('http://127.0.0.1:8000/docs/index.html', { waitUntil: 'networkidle2', timeout: 10000 });

        console.log("Waiting for episode manifest & clip durations probing...");
        await new Promise(r => setTimeout(r, 4500));

        // 🧪 TEST 1: Dropdown Menu Deduplication & Episode Options Check
        console.log("\n🧪 TEST 1: Dropdown Menu Manifest & Option Deduplication...");
        const selectState = await page.evaluate(() => {
            const selectEl = document.getElementById('episodeSelect');
            if (!selectEl) return { count: 0, options: [] };
            const opts = Array.from(selectEl.options).map(o => ({ value: o.value, text: o.text.trim() }));
            return {
                count: opts.length,
                options: opts
            };
        });

        console.log(`- Dropdown Options Count: ${selectState.count}`);
        selectState.options.forEach(opt => console.log(`  └─ Option [${opt.value}]: "${opt.text}"`));

        const optionValues = selectState.options.map(o => o.value);
        const hasDuplicates = new Set(optionValues).size !== optionValues.length;
        if (hasDuplicates) {
            throw new Error("FAIL: Duplicate episode options detected in dropdown menu!");
        }

        // 🧪 TEST 2: Baseline State & Clip List Rendering
        console.log("\n🧪 TEST 2: Baseline Player Checklist...");
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

        console.log(`- Timeline Total Duration Label: ${state.totalTimeText}`);
        console.log(`- Sidebar Clip Cards Rendered: ${state.clipsCount}`);
        console.log(`- Video Element Source: ${state.videoSrc}`);

        if (state.clipsCount === 0) {
            throw new Error("FAIL: Sidebar clips were not rendered!");
        }
        if (state.totalTimeText === "0:00" || state.totalTimeText === "") {
            throw new Error("FAIL: Total duration label was not populated!");
        }
        if (!state.videoSrc || !state.videoSrc.includes('245-')) {
            throw new Error(`FAIL: Video player source ${state.videoSrc} did not load episode 245 clip video!`);
        }

        // 🧪 TEST 3: Sidebar Clip Switching & Video Player Source Synchronization
        console.log("\n🧪 TEST 3: Sidebar Clip Switching & Source Sync...");
        const secondClipSelector = '.clip-item:nth-child(2)';
        await page.waitForSelector(secondClipSelector);
        await page.click(secondClipSelector);
        await new Promise(r => setTimeout(r, 1500));

        const clip2State = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const activeCard = document.querySelector('.clip-item.active');
            return {
                videoSrc: videoEl ? videoEl.src : null,
                activeCardId: activeCard ? activeCard.id : null
            };
        });

        console.log(`- Active Clip Card ID: ${clip2State.activeCardId}`);
        console.log(`- Video Element Source after switching: ${clip2State.videoSrc}`);

        if (!clip2State.videoSrc || !clip2State.videoSrc.includes('245-')) {
            throw new Error(`FAIL: Video player source ${clip2State.videoSrc} did not load episode video!`);
        }

        // Switch back to 1st Clip
        await page.click('.clip-item:nth-child(1)');
        await new Promise(r => setTimeout(r, 1000));

        // 🧪 TEST 4: Playback Controls & Skip Buttons
        console.log("\n🧪 TEST 4: Playback Controls & Skip Verification...");
        await page.click('#playBtn');
        await new Promise(r => setTimeout(r, 2500));

        const playState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const statusTxt = document.getElementById('viewportStatus').textContent;
            return {
                videoPaused: videoEl ? videoEl.paused : null,
                videoCurrentTime: videoEl ? videoEl.currentTime : null,
                statusText: statusTxt
            };
        });

        console.log(`- Viewport Status: ${playState.statusText}`);
        console.log(`- Video Current Time: ${playState.videoCurrentTime}s`);

        if (playState.statusText !== 'Playing' || playState.videoPaused) {
            throw new Error("FAIL: Video failed to start playing!");
        }

        // Skip Forward
        const prevTime = playState.videoCurrentTime;
        await page.click('#skipForwardBtn');
        await new Promise(r => setTimeout(r, 1000));

        const skipState = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            return videoEl ? videoEl.currentTime : 0;
        });
        console.log(`- Video Time after Skip Forward: ${skipState}s (was ${prevTime}s)`);
        if (skipState < prevTime + 12.0) {
            throw new Error("FAIL: Skip forward did not advance playhead!");
        }

        // Pause
        await page.click('#playBtn');
        await new Promise(r => setTimeout(r, 1000));

        // 🧪 TEST 5: Episode Switcher Dropdown Interaction
        console.log("\n🧪 TEST 5: Episode Switcher Dropdown Interaction...");
        if (optionValues.includes('244')) {
            await page.select('#episodeSelect', '244');
            await new Promise(r => setTimeout(r, 3000));

            const ep244State = await page.evaluate(() => {
                const videoEl = document.getElementById('videoPlayer');
                const clipCards = document.querySelectorAll('.clip-item');
                return {
                    clipsCount: clipCards.length,
                    videoSrc: videoEl ? videoEl.src : null
                };
            });
            console.log(`- Episode 244 Clip Cards Count: ${ep244State.clipsCount}`);
            console.log(`- Episode 244 Video Source: ${ep244State.videoSrc}`);

            if (ep244State.clipsCount === 0 || !ep244State.videoSrc.includes('244-1.mp4')) {
                throw new Error("FAIL: Failed to switch episode to Episode 244!");
            }

            // Switch back to Episode 245
            await page.select('#episodeSelect', '245');
            await new Promise(r => setTimeout(r, 3000));
        }

        if (capturedErrors.length > 0) {
            throw new Error(`FAIL: Captured ${capturedErrors.length} unhandled player browser error(s):\n` + capturedErrors.join('\n'));
        }

        console.log("\n✅ ALL COMPREHENSIVE EDITOR PREVIEW REGRESSION TESTS PASSED 100%!");

    } catch (err) {
        console.error("\n❌ TEST FAILURE DETECTED:");
        console.error(err.message);
        process.exit(1);
    } finally {
        await browser.close();
    }
}

runTest();
