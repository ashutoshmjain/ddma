const puppeteer = require('puppeteer');

async function runTest() {
    console.log("🚀 Starting Headless Browser Curator Test...");
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ]
    });
    const page = await browser.newPage();

    // Capture console errors/logs
    page.on('console', msg => {
        console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
    });

    page.on('pageerror', err => {
        console.error(`[Browser Page Error] ${err.stack}`);
    });

    try {
        console.log("Navigating to http://127.0.0.1:8000/curator.html ...");
        await page.goto('http://127.0.0.1:8000/curator.html', { waitUntil: 'domcontentloaded', timeout: 8000 }).catch(e => {
            console.log("Page load timeout (ignored as expected):", e.message);
        });

        // Wait 4 seconds for page script execution
        console.log("Waiting for workspace to initialize...");
        await new Promise(r => setTimeout(r, 4000));

        // Test Action: Open and Close the Video Preview Modal
        console.log("\n🧪 Running Modal Open/Close Verification Test...");
        
        // 1. Open the modal programmatically
        await page.evaluate(() => {
            const overlay = document.getElementById('videoModalOverlay');
            const videoEl = document.getElementById('previewVideoPlayer');
            overlay.classList.add('active');
            videoEl.src = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA"; // mock source
        });
        
        const openState = await page.evaluate(() => {
            return document.getElementById('videoModalOverlay').classList.contains('active');
        });
        console.log(`- Modal Active after open: ${openState}`);
        
        // 2. Click the close button via Puppeteer mouse simulation!
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

        console.log("📊 Modal Test Results:");
        console.log(`- Modal Active After Close Button Click: ${closedState.active}`);
        console.log(`- Video Player Source Cleared: ${closedState.videoSourceCleared}`);

        if (closedState.active) {
            throw new Error("FAIL: Video modal overlay failed to close after physical click!");
        }
        if (!closedState.videoSourceCleared) {
            throw new Error("FAIL: Video element source was not cleared on close!");
        }

        // 3. Test AI Bridge Card Reviewer Modal
        console.log("\n🧪 Running AI Bridge Reviewer Prompt Modal Verification Test...");
        await page.click('#reviewBridgesBtn');
        await new Promise(r => setTimeout(r, 2000));

        const bridgeModalState = await page.evaluate(() => {
            const overlay = document.getElementById('bridgeReviewModalOverlay');
            const textarea = document.getElementById('bridgeReviewPromptTextarea');
            return {
                active: overlay ? overlay.classList.contains('active') : false,
                hasPromptText: textarea ? textarea.value.length > 50 : false
            };
        });

        console.log(`- AI Bridge Reviewer Modal Active after click: ${bridgeModalState.active}`);
        console.log(`- Prompt Textarea populated with context prompt: ${bridgeModalState.hasPromptText}`);

        if (!bridgeModalState.active) {
            throw new Error("FAIL: AI Bridge Reviewer modal did not open!");
        }
        if (!bridgeModalState.hasPromptText) {
            throw new Error("FAIL: AI Bridge Reviewer prompt textarea was empty!");
        }

        // Close AI Bridge Reviewer Modal
        await page.click('#closeBridgeReviewModalBtn');
        await new Promise(r => setTimeout(r, 500));

        const bridgeModalClosed = await page.evaluate(() => {
            const overlay = document.getElementById('bridgeReviewModalOverlay');
            return overlay ? !overlay.classList.contains('active') : true;
        });

        console.log(`- AI Bridge Reviewer Modal Active after close click: ${!bridgeModalClosed}`);
        if (!bridgeModalClosed) {
            throw new Error("FAIL: AI Bridge Reviewer modal failed to close!");
        }

        console.log("\n✅ ALL CURATOR MODAL TESTS PASSED SUCCESSFULLY!");

    } catch (err) {
        console.error("\n❌ TEST FAILURE DETECTED:");
        console.error(err.message);
        process.exit(1);
    } finally {
        await browser.close();
    }
}

runTest();
