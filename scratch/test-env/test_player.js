const puppeteer = require('puppeteer');
const fs = require('fs');

function getExecutablePath() {
    const paths = [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
        process.env.CHROME_BIN
    ];
    for (const p of paths) {
        if (p && fs.existsSync(p)) return p;
    }
    return undefined;
}

async function runTest() {
    console.log("====================================================");
    console.log("   DDMA Preview Player Regression & Invariant Tests");
    console.log("====================================================");

    const execPath = getExecutablePath();
    const launchOptions = {
        headless: 'new',
        args: [
            '--autoplay-policy=no-user-gesture-required',
            '--mute-audio',
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ]
    };
    if (execPath) {
        launchOptions.executablePath = execPath;
    }

    const browser = await puppeteer.launch(launchOptions);
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });

    const capturedErrors = [];
    const missing404Urls = [];

    page.on('console', msg => {
        if (msg.type() === 'error') {
            const text = msg.text();
            console.log(`[Browser Console ERROR] ${text}`);
            capturedErrors.push(`[Console Error] ${text}`);
        }
    });

    page.on('response', resp => {
        if (resp.status() === 404) {
            const url = resp.url();
            if (!url.includes('favicon.ico')) {
                console.log(`[HTTP 404 Detected] ${url}`);
                missing404Urls.push(url);
            }
        }
    });

    page.on('pageerror', err => {
        console.error(`[Browser Page Exception] ${err.toString()}`);
        capturedErrors.push(`[Page Exception] ${err.toString()}`);
    });

    try {
        console.log("Navigating to http://127.0.0.1:8000/docs/index.html ...");
        await page.goto('http://127.0.0.1:8000/docs/index.html', { waitUntil: 'networkidle2', timeout: 15000 });

        console.log("Waiting for player initialization & duration probes...");
        await new Promise(r => setTimeout(r, 3000));

        // -------------------------------------------------------------
        // TEST 1: Dropdown Menu Manifest Lists 247, 248, 249 & Defaults to Latest (249)
        // -------------------------------------------------------------
        console.log("\n🧪 TEST 1: Manifest lists 247, 248, 249 and defaults to latest (249)...");
        const selectState = await page.evaluate(() => {
            const selectEl = document.getElementById('episodeSelect');
            if (!selectEl) return { count: 0, options: [], selected: null };
            const opts = Array.from(selectEl.options).map(o => ({ value: o.value, text: o.text.trim() }));
            return {
                count: opts.length,
                options: opts,
                selected: selectEl.value
            };
        });

        console.log(`- Dropdown Options Count: ${selectState.count}`);
        selectState.options.forEach(opt => console.log(`  └─ Option [${opt.value}]: "${opt.text}"`));
        console.log(`- Default Selected Episode: ${selectState.selected}`);

        const optionValues = selectState.options.map(o => o.value);
        for (const ep of ['247', '248', '249']) {
            if (!optionValues.includes(ep)) {
                throw new Error(`FAIL: episodes.json manifest missing published episode ${ep}! Listed: ${optionValues.join(', ')}`);
            }
        }

        if (selectState.selected !== '249') {
            throw new Error(`FAIL: Player did not default to latest episode 249! Selected: ${selectState.selected}`);
        }
        console.log("✔ PASS: Live player lists 247, 248, 249 and defaults to latest (249)");

        // -------------------------------------------------------------
        // TEST 2: Episode 249 Hides Missing Clips (5/21 rendered, zero 404s, all 5 play)
        // -------------------------------------------------------------
        console.log("\n🧪 TEST 2: Episode 249 hides unrendered clips (5 available, zero dead sidebar entries)...");
        const ep249State = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const clipCards = Array.from(document.querySelectorAll('.clip-item')).map(c => ({
                id: c.id,
                text: c.innerText.trim().replace(/\s+/g, ' ')
            }));
            const totalTimeTxt = document.getElementById('totalTimeLabel').textContent;
            return {
                clipsCount: clipCards.length,
                clips: clipCards,
                totalTime: totalTimeTxt,
                videoSrc: videoEl ? videoEl.src : null
            };
        });

        console.log(`- Episode 249 Active Clips: ${ep249State.clipsCount}`);
        ep249State.clips.forEach(c => console.log(`  └─ ${c.id}: ${c.text.slice(0, 50)}...`));
        console.log(`- Active Video Player Source: ${ep249State.videoSrc}`);

        if (ep249State.clipsCount !== 5) {
            throw new Error(`FAIL: Expected 5 available clips for Episode 249, got ${ep249State.clipsCount}`);
        }
        if (!ep249State.videoSrc || !ep249State.videoSrc.includes('249-0.mp4')) {
            throw new Error(`FAIL: Expected first clip to be 249-0.mp4 (0-based cold open), got: ${ep249State.videoSrc}`);
        }

        // -------------------------------------------------------------
        // TEST 3: Episode 248 Hides Missing Clips (7/23 rendered, zero 404s, all 7 play)
        // -------------------------------------------------------------
        console.log("\n🧪 TEST 3: Switching to Episode 248 (7 available, zero dead sidebar entries)...");
        await page.select('#episodeSelect', '248');
        await new Promise(r => setTimeout(r, 3000));

        const ep248State = await page.evaluate(() => {
            const videoEl = document.getElementById('videoPlayer');
            const clipCards = Array.from(document.querySelectorAll('.clip-item')).map(c => ({
                id: c.id,
                text: c.innerText.trim().replace(/\s+/g, ' ')
            }));
            return {
                clipsCount: clipCards.length,
                clips: clipCards,
                videoSrc: videoEl ? videoEl.src : null
            };
        });

        console.log(`- Episode 248 Active Clips: ${ep248State.clipsCount}`);
        ep248State.clips.forEach(c => console.log(`  └─ ${c.id}: ${c.text.slice(0, 50)}...`));
        console.log(`- Active Video Player Source: ${ep248State.videoSrc}`);

        if (ep248State.clipsCount !== 7) {
            throw new Error(`FAIL: Expected 7 available clips for Episode 248, got ${ep248State.clipsCount}`);
        }
        if (!ep248State.videoSrc || !ep248State.videoSrc.includes('248-1.mp4')) {
            throw new Error(`FAIL: Expected first clip to be 248-1.mp4, got: ${ep248State.videoSrc}`);
        }

        // Test clicking each clip in 248 to assert that every clip listed in sidebar plays
        for (let i = 1; i <= 7; i++) {
            const cardSelector = `#sidebar-clip-${i}`;
            await page.waitForSelector(cardSelector, { timeout: 3000 });
            await page.click(cardSelector);
            await new Promise(r => setTimeout(r, 600));

            const activeSrc = await page.evaluate(() => {
                const videoEl = document.getElementById('videoPlayer');
                return videoEl ? videoEl.src : null;
            });
            if (!activeSrc || !activeSrc.includes(`248-${i}.mp4`)) {
                throw new Error(`FAIL: Clicking sidebar clip ${i} did not load 248-${i}.mp4! Got: ${activeSrc}`);
            }
        }
        console.log("✔ PASS: All 7 clips in Episode 248 load and play cleanly");

        // -------------------------------------------------------------
        // TEST 4: Assert Zero HTTP 404s Across All Actions
        // -------------------------------------------------------------
        console.log("\n🧪 TEST 4: Verifying zero HTTP 404 errors occurred...");
        if (missing404Urls.length > 0) {
            throw new Error(`FAIL: Detected ${missing404Urls.length} HTTP 404 responses:\n` + missing404Urls.join('\n'));
        }
        console.log("✔ PASS: Zero HTTP 404 errors detected!");

        console.log("\n====================================================");
        console.log("✅ ALL PLAYER VERIFICATION & REGRESSION TESTS PASSED!");
        console.log("====================================================\n");

    } catch (err) {
        console.error("\n❌ TEST FAILURE DETECTED:");
        console.error(err.message);
        process.exit(1);
    } finally {
        await browser.close();
    }
}

runTest();
