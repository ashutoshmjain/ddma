const puppeteer = require('puppeteer');
const { execSync } = require('child_process');
const fs = require('fs');

async function runTest() {
    console.log("🚀 Starting Comprehensive Headless Browser Curator Regression Suite...");
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ]
    });
    const page = await browser.newPage();

    const capturedErrors = [];

    // Capture console errors and page errors
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
        console.error(`[Browser Page Exception] ${err.message}`);
        capturedErrors.push(`[Page Exception] ${err.message}`);
    });

    try {
        console.log("Navigating to http://127.0.0.1:8000/curator.html ...");
        await page.goto('http://127.0.0.1:8000/curator.html', { waitUntil: 'domcontentloaded', timeout: 10000 }).catch(e => {
            console.log("Page load timeout (ignored as expected):", e.message);
        });

        console.log("Waiting for workspace to initialize and clips to load...");
        await page.waitForSelector('.clip-card', { timeout: 10000 });
        await new Promise(r => setTimeout(r, 2000));

        // 🧪 TEST 0: Verifying Persistent Top-Line Header Bar Elements
        console.log("\n🧪 TEST 0: Verifying Persistent Top-Line Header Bar & Episode Switcher...");
        const topbarState = await page.evaluate(() => {
            const topbar = document.querySelector('.app-topbar');
            const select = document.getElementById('topEpisodeSelect');
            const topSettingsBtn = document.getElementById('topSettingsBtn');
            const teamBadge = document.querySelector('.team-badge');
            return {
                topbarVisible: topbar !== null && topbar.offsetParent !== null,
                selectOptionsCount: select ? select.options.length : 0,
                selectedEpisode: select ? select.value : null,
                topSettingsBtnVisible: topSettingsBtn !== null && topSettingsBtn.offsetParent !== null,
                teamBadgeText: teamBadge ? teamBadge.textContent.trim() : null
            };
        });

        console.log(`- Topbar Visible: ${topbarState.topbarVisible}`);
        console.log(`- Episode Select Options: ${topbarState.selectOptionsCount} (Selected: ${topbarState.selectedEpisode})`);
        console.log(`- Top Settings Button Visible: ${topbarState.topSettingsBtnVisible}`);
        console.log(`- Team Badge: "${topbarState.teamBadgeText}"`);

        if (!topbarState.topbarVisible || topbarState.selectOptionsCount === 0 || !topbarState.topSettingsBtnVisible) {
            throw new Error("FAIL: Persistent Top-Line Header Bar elements missing or unpopulated!");
        }

        // 🧪 TEST 1: Title Card Input Editing (No premature auto-compile gray-out)
        console.log("\n🧪 TEST 1: Editing Title Input & Verifying State Stability...");
        const titleInputSelector = '.clip-card[data-index="0"] .clip-card-title';
        await page.waitForSelector(titleInputSelector);
        
        await page.focus(titleInputSelector);
        await page.keyboard.type(' Test Edit Title', { delay: 20 });
        await page.evaluate(sel => document.querySelector(sel).blur(), titleInputSelector);
        await new Promise(r => setTimeout(r, 1000));

        const cardState = await page.evaluate(() => {
            const card1 = document.querySelector('.clip-card[data-index="0"]');
            return {
                isProcessing: card1 ? card1.textContent.includes('Processing...') : false,
                isCollapsed: card1 ? card1.classList.contains('collapsed') : false
            };
        });
        console.log(`- Card Processing State after blur: ${cardState.isProcessing}`);
        if (cardState.isProcessing) {
            throw new Error("FAIL: Clip card entered premature processing state while editing title!");
        }

        // 🧪 TEST 2: Music Segment Volume Slider Editing (Zero DOMExceptions on blur/remove)
        console.log("\n🧪 TEST 2: Music Segment Volume Editing & DOM Node Safety...");
        const musicVolumeSelector = '.clip-card[data-index="0"] .music-volume';
        const musicVolEl = await page.$(musicVolumeSelector);

        if (musicVolEl) {
            await page.focus(musicVolumeSelector);
            await page.keyboard.press('Backspace');
            await page.keyboard.type('0.85');
            await page.evaluate(sel => {
                const el = document.querySelector(sel);
                if (el) {
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.blur();
                }
            }, musicVolumeSelector);
            await new Promise(r => setTimeout(r, 1000));
            console.log("- Music volume updated without DOM Exceptions.");
        } else {
            console.log("- Note: Clip 1 has no .music-volume input directly visible, skipping slider input step.");
        }

        // 🧪 TEST 2b: Mosaic & Video Button Lock Protection Rules
        console.log("\n🧪 TEST 2b: Verifying Video Button Availability (Unlocked) & Mosaic Lock Protection...");
        
        // Ensure clip 1 is unlocked for testing
        await page.evaluate(() => {
            if (clips[0]) {
                clips[0].locked = false;
                renderClips();
            }
        });
        await new Promise(r => setTimeout(r, 500));

        const unlockedStates = await page.evaluate(() => {
            const card1 = document.querySelector('.clip-card[data-index="0"]');
            if (!card1) return { videoDisabled: true, mosaicDisabled: false, videoText: '', mosaicText: '' };
            const videoBtn = card1.querySelector('.btn-card-video');
            const mosaicBtn = card1.querySelector('.btn-card-mosaic');
            return {
                videoDisabled: videoBtn ? videoBtn.disabled : true,
                mosaicDisabled: mosaicBtn ? mosaicBtn.disabled : false,
                videoText: videoBtn ? videoBtn.textContent.trim() : '',
                mosaicText: mosaicBtn ? mosaicBtn.textContent.trim() : ''
            };
        });

        console.log(`- Unlocked Clip 1 -> Video Button: "${unlockedStates.videoText}" | Disabled: ${unlockedStates.videoDisabled} (Expected: false)`);
        console.log(`- Unlocked Clip 1 -> Mosaic Button: "${unlockedStates.mosaicText}" | Disabled: ${unlockedStates.mosaicDisabled} (Expected: true)`);

        if (unlockedStates.videoDisabled) {
            throw new Error("FAIL: Video button is grayed out / disabled on unlocked Clip 1!");
        }
        if (!unlockedStates.mosaicDisabled) {
            throw new Error("FAIL: Mosaic button should be disabled when clip is unlocked to protect against premature Mosaic renders!");
        }

        // Lock clip 1 and verify Mosaic becomes enabled
        await page.evaluate(() => {
            if (clips[0]) {
                clips[0].locked = true;
                renderClips();
            }
        });
        await new Promise(r => setTimeout(r, 500));

        const lockedStates = await page.evaluate(() => {
            const card1 = document.querySelector('.clip-card[data-index="0"]');
            const mosaicBtn = card1 ? card1.querySelector('.btn-card-mosaic') : null;
            return {
                mosaicDisabled: mosaicBtn ? mosaicBtn.disabled : true
            };
        });

        console.log(`- Locked Clip 1 -> Mosaic Button Disabled: ${lockedStates.mosaicDisabled} (Expected: false)`);
        if (lockedStates.mosaicDisabled) {
            throw new Error("FAIL: Mosaic button did not enable after locking clip 1!");
        }

        // Check for any captured JS page errors during interactions
        if (capturedErrors.length > 0) {
            throw new Error(`FAIL: Captured ${capturedErrors.length} unhandled browser error(s):\n` + capturedErrors.join('\n'));
        }

        // 🧪 TEST 3: Modal Open/Close Verification Test
        console.log("\n🧪 TEST 3: Running Modal Open/Close Verification Test...");
        await page.evaluate(() => {
            const overlay = document.getElementById('videoModalOverlay');
            const videoEl = document.getElementById('previewVideoPlayer');
            overlay.classList.add('active');
            videoEl.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
        });

        console.log("Simulating physical mouse click on Close button (#closeVideoModalBtn)...");
        await page.click('#closeVideoModalBtn');
        await new Promise(r => setTimeout(r, 1000));

        const closedState = await page.evaluate(() => {
            const overlay = document.getElementById('videoModalOverlay');
            const videoEl = document.getElementById('previewVideoPlayer');
            return {
                active: overlay.classList.contains('active'),
                videoSourceCleared: (videoEl.src === "" || videoEl.src === window.location.href)
            };
        });

        console.log(`- Modal Active After Close Click: ${closedState.active}`);
        console.log(`- Video Player Source Cleared: ${closedState.videoSourceCleared}`);

        if (closedState.active) {
            throw new Error("FAIL: Video modal overlay failed to close after click!");
        }
        if (!closedState.videoSourceCleared) {
            throw new Error("FAIL: Video element source was not cleared on close!");
        }

        // 🧪 TEST 4: AI Bridge Card Reviewer Modal
        console.log("\n🧪 TEST 4: Running AI Bridge Reviewer Prompt Modal Verification Test...");
        await page.click('#reviewBridgesBtn');
        await new Promise(r => setTimeout(r, 1500));

        const bridgeModalState = await page.evaluate(() => {
            const overlay = document.getElementById('bridgeReviewModalOverlay');
            const textarea = document.getElementById('bridgeReviewPromptTextarea');
            return {
                active: overlay ? overlay.classList.contains('active') : false,
                hasPromptText: textarea ? textarea.value.length > 50 : false
            };
        });

        console.log(`- AI Bridge Reviewer Modal Active: ${bridgeModalState.active}`);
        console.log(`- Prompt Textarea populated: ${bridgeModalState.hasPromptText}`);

        if (!bridgeModalState.active || !bridgeModalState.hasPromptText) {
            throw new Error("FAIL: AI Bridge Reviewer modal failed verification!");
        }

        await page.click('#closeBridgeReviewModalBtn');
        await new Promise(r => setTimeout(r, 500));

        // 🧪 TEST 5: Media Stream Verification (FFprobe Audio/Video Alignment)
        console.log("\n🧪 TEST 5: Verifying Compiled Media File Audio/Video Alignment via FFprobe...");
        const clip1Video = "clips/245-1.mp4";
        if (fs.existsSync(clip1Video)) {
            const probeJsonStr = execSync(`ffprobe -v error -show_streams -of json ${clip1Video}`).toString();
            const probeData = JSON.parse(probeJsonStr);
            const videoStream = probeData.streams.find(s => s.codec_type === 'video');
            const audioStream = probeData.streams.find(s => s.codec_type === 'audio');

            const vDur = parseFloat(videoStream.duration || 0);
            const aDur = parseFloat(audioStream.duration || 0);

            console.log(`- Video Stream Present: ${!!videoStream} (${videoStream ? videoStream.codec_name : 'none'}, duration: ${vDur.toFixed(2)}s)`);
            console.log(`- Audio Stream Present: ${!!audioStream} (${audioStream ? audioStream.codec_name + ' @ ' + audioStream.sample_rate + 'Hz' : 'none'}, duration: ${aDur.toFixed(2)}s)`);

            if (!videoStream || !audioStream) {
                throw new Error("FAIL: Compiled video is missing required video or audio stream!");
            }
            if (audioStream.sample_rate !== '48000') {
                throw new Error(`FAIL: Audio sample rate ${audioStream.sample_rate}Hz does not match required 48000Hz!`);
            }
            if (Math.abs(vDur - aDur) > 0.25) {
                throw new Error(`FAIL: Video stream duration (${vDur.toFixed(2)}s) and audio stream duration (${aDur.toFixed(2)}s) are desynced by > 0.25s!`);
            }
        } else {
            console.log(`- Note: ${clip1Video} not found on disk, skipping media stream probe.`);
        }

        console.log("\n✅ ALL COMPREHENSIVE CURATOR REGRESSION TESTS PASSED 100%!");

    } catch (err) {
        console.error("\n❌ TEST FAILURE DETECTED:");
        console.error(err.message);
        process.exit(1);
    } finally {
        await browser.close();
    }
}

runTest();
