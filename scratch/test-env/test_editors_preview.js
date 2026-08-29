const puppeteer = require('puppeteer');

async function runEditorsPreviewTests() {
    console.log("🚀 Starting Dual-Channel (Desktop & Mobile) Puppeteer Regression Suite for Editor's Preview...");

    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    page.setDefaultTimeout(60000);

    const capturedErrors = [];
    page.on('console', msg => {
        const text = msg.text();
        if (msg.type() === 'error' && !text.includes('404') && !text.includes('favicon.ico')) {
            console.log(`[Browser Console ERROR] ${text}`);
            capturedErrors.push(`[Console Error] ${text}`);
        }
    });

    page.on('pageerror', err => {
        console.error(`[Browser Page Exception] ${err.message}`);
        capturedErrors.push(`[Page Exception] ${err.message}`);
    });

    try {
        // =========================================================================
        // 🖥️ CHANNEL 1: DESKTOP INTERFACE (1280 x 800)
        // =========================================================================
        console.log("\n=========================================================================");
        console.log("🖥️  CHANNEL 1: Testing Desktop Content Delivery (1280 x 800)");
        console.log("=========================================================================");

        await page.setViewport({ width: 1280, height: 800, isMobile: false, hasTouch: false });
        console.log("Navigating to http://127.0.0.1:8000/docs/index.html?ep=245 ...");
        await page.goto('http://127.0.0.1:8000/docs/index.html?ep=245', { waitUntil: 'domcontentloaded' });

        console.log("Waiting for storyboard chapters and canvas to initialize...");
        await page.waitForFunction(() => document.querySelectorAll('.clip-item').length > 0, { timeout: 15000 });
        await new Promise(r => setTimeout(r, 1000));

        // 🧪 TEST D1: Desktop Layout & Warm Sand Branding
        console.log("\n🧪 TEST D1: Verifying Desktop Layout Grid & Warm Sand Branding...");
        const desktopState = await page.evaluate(() => {
            const wordmark = document.querySelector('.brand-wordmark');
            const layout = document.querySelector('.main-content-layout');
            const layoutDisplay = window.getComputedStyle(layout).display;
            const layoutCols = window.getComputedStyle(layout).gridTemplateColumns;
            const sidebar = document.querySelector('.sidebar');
            const workspace = document.querySelector('.workspace');
            const volumeContainer = document.querySelector('.volume-container');
            const episodeSelect = document.getElementById('episodeSelect');
            const clipsCount = document.querySelectorAll('.clip-item').length;

            return {
                wordmark: wordmark ? wordmark.textContent.replace(/\s+/g, ' ').trim() : '',
                layoutDisplay,
                layoutCols,
                sidebarVisible: sidebar !== null && window.getComputedStyle(sidebar).display !== 'none',
                workspaceVisible: workspace !== null && window.getComputedStyle(workspace).display !== 'none',
                volumeVisible: volumeContainer !== null && window.getComputedStyle(volumeContainer).display !== 'none',
                selectedEpisode: episodeSelect ? episodeSelect.value : null,
                clipsCount
            };
        });

        console.log(`- Wordmark Text: "${desktopState.wordmark}"`);
        console.log(`- Layout Display: ${desktopState.layoutDisplay} (Columns: ${desktopState.layoutCols})`);
        console.log(`- Sidebar Visible: ${desktopState.sidebarVisible}`);
        console.log(`- Workspace Visible: ${desktopState.workspaceVisible}`);
        console.log(`- Volume Slider Visible: ${desktopState.volumeVisible} (Expected: true for desktop)`);
        console.log(`- Active Episode: ${desktopState.selectedEpisode}`);
        console.log(`- Storyboard Chapters Loaded: ${desktopState.clipsCount}`);

        if (!desktopState.wordmark.replace(/\s+/g, '').includes('SHUTRIINFOGRAPHICS')) {
            throw new Error("FAIL: Desktop branding wordmark is missing or incorrect!");
        }
        if (desktopState.layoutDisplay !== 'grid' || !desktopState.volumeVisible || desktopState.clipsCount === 0) {
            throw new Error("FAIL: Desktop 2-column grid layout or chapter items failed to initialize!");
        }

        // 🧪 TEST D2: Desktop Playback & Seeking Interaction
        console.log("\n🧪 TEST D2: Testing Desktop Play/Pause and Seek Bar...");
        await page.click('#playBtn');
        await new Promise(r => setTimeout(r, 800));

        const isPlayingAfterClick = await page.evaluate(() => {
            const playBtn = document.getElementById('playBtn');
            return isPlaying === true || (playBtn && playBtn.innerHTML.includes('pause'));
        });
        console.log(`- Play state active after click: ${isPlayingAfterClick}`);

        // Pause
        await page.click('#playBtn');
        await new Promise(r => setTimeout(r, 400));

        // Skip 15s forward
        await page.click('#skipForwardBtn');
        await new Promise(r => setTimeout(r, 400));

        // 🧪 TEST D3: Storyboard Chapter Selection
        console.log("\n🧪 TEST D3: Testing Storyboard Chapter Item Switching...");
        const chapterSwitch = await page.evaluate(() => {
            const secondItem = document.querySelectorAll('.clip-item')[1];
            if (secondItem) {
                secondItem.click();
                return {
                    clicked: true,
                    title: secondItem.querySelector('.clip-meta-title')?.textContent.trim()
                };
            }
            return { clicked: false, title: '' };
        });
        console.log(`- Switched to Chapter 2: "${chapterSwitch.title}"`);
        await new Promise(r => setTimeout(r, 600));

        // =========================================================================
        // 📱 CHANNEL 2: MOBILE INTERFACE (390 x 844 - iPhone 14/15)
        // =========================================================================
        console.log("\n=========================================================================");
        console.log("📱 CHANNEL 2: Testing Mobile Content Delivery (390 x 844)");
        console.log("=========================================================================");

        await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
        console.log("Reloading under mobile viewport conditions...");
        await page.goto('http://127.0.0.1:8000/docs/index.html?ep=245', { waitUntil: 'domcontentloaded' });
        await page.waitForFunction(() => document.querySelectorAll('.clip-item').length > 0, { timeout: 15000 });
        await new Promise(r => setTimeout(r, 1000));

        // 🧪 TEST M1: Mobile Vertical Stack Layout & Responsiveness
        console.log("\n🧪 TEST M1: Verifying Mobile Vertical Stack & Touch Adaptations...");
        const mobileState = await page.evaluate(() => {
            const layout = document.querySelector('.main-content-layout');
            const layoutFlex = window.getComputedStyle(layout).flexDirection;
            const volumeContainer = document.querySelector('.volume-container');
            const modeToggle = document.querySelector('.mode-toggle-card');
            const canvasWrapper = document.querySelector('.canvas-wrapper');
            const canvasRect = canvasWrapper ? canvasWrapper.getBoundingClientRect() : null;
            const controlsCard = document.querySelector('.controls-card');
            const sidebar = document.querySelector('.sidebar');

            return {
                layoutFlex,
                volumeHidden: volumeContainer ? window.getComputedStyle(volumeContainer).display === 'none' : true,
                modeToggleHidden: modeToggle ? window.getComputedStyle(modeToggle).display === 'none' : true,
                canvasWidth: canvasRect ? canvasRect.width : 0,
                canvasHeight: canvasRect ? canvasRect.height : 0,
                controlsVisible: controlsCard !== null && window.getComputedStyle(controlsCard).display !== 'none',
                sidebarVisible: sidebar !== null && window.getComputedStyle(sidebar).display !== 'none'
            };
        });

        console.log(`- Mobile Layout Direction: ${mobileState.layoutFlex} (Expected: column)`);
        console.log(`- Volume Slider Hidden on Mobile: ${mobileState.volumeHidden} (Expected: true)`);
        console.log(`- Mode Toggle Hidden on Mobile: ${mobileState.modeToggleHidden} (Expected: true)`);
        console.log(`- Viewport Canvas Size: ${mobileState.canvasWidth.toFixed(1)}px x ${mobileState.canvasHeight.toFixed(1)}px (Square 1:1)`);
        console.log(`- Thumb-friendly Controls Visible: ${mobileState.controlsVisible}`);
        console.log(`- Storyboard Playlist Below Controls: ${mobileState.sidebarVisible}`);

        if (mobileState.layoutFlex !== 'column' || !mobileState.volumeHidden || !mobileState.controlsVisible) {
            throw new Error("FAIL: Mobile layout adaptations failed!");
        }

        // 🧪 TEST M2: Mobile Touch Playback & Seeking
        console.log("\n🧪 TEST M2: Testing Mobile Touch Tap Play/Pause...");
        await page.tap('#playBtn');
        await new Promise(r => setTimeout(r, 800));
        await page.tap('#playBtn');
        await new Promise(r => setTimeout(r, 400));
        console.log("- Mobile touch interactions executed cleanly.");

        // 🧪 TEST M3: Mobile Chapter Tap
        console.log("\n🧪 TEST M3: Testing Mobile Chapter Tap & Selection...");
        await page.evaluate(() => {
            const thirdItem = document.querySelectorAll('.clip-item')[2];
            if (thirdItem) thirdItem.click();
        });
        await new Promise(r => setTimeout(r, 600));

        const activeIndex = await page.evaluate(() => activeTimelineIndex);
        console.log(`- Active Chapter Index after mobile tap: ${activeIndex}`);

        // Error verification
        if (capturedErrors.length > 0) {
            throw new Error(`FAIL: Captured ${capturedErrors.length} unhandled browser error(s):\n` + capturedErrors.join('\n'));
        }

        console.log("\n=========================================================================");
        console.log("🎉 ALL DUAL-CHANNEL (DESKTOP & MOBILE) REGRESSION TESTS PASSED!");
        console.log("=========================================================================\n");

    } finally {
        await browser.close();
    }
}

runEditorsPreviewTests().catch(err => {
    console.error("\n❌ TEST SUITE FAILURE:", err.message);
    process.exit(1);
});
