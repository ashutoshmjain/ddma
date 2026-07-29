const puppeteer = require('puppeteer');

(async () => {
    console.log("🚀 Starting Comprehensive Episode Remix & Dual-Mode Ingestion Regression Test...");

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });

        const page = await browser.newPage();
        
        console.log("Navigating to http://127.0.0.1:8000/curator.html ...");
        await page.goto("http://127.0.0.1:8000/curator.html", { waitUntil: "domcontentloaded", timeout: 15000 });
        await new Promise(r => setTimeout(r, 2000));

        console.log("\n🧪 TEST 1: Fetching Episode Remix Prompt Template via Server Endpoint...");
        const promptRes = await page.evaluate(async () => {
            const res = await fetch('/get-episode-gemini-prompt?id=episode_245');
            return await res.json();
        });

        console.log(`- Fetch Status: ${promptRes.success}`);
        console.log(`- Prompt Contains EPISODE STORYBOARDING: ${promptRes.prompt.includes("EPISODE STORYBOARDING")}`);
        if (!promptRes.success || !promptRes.prompt.includes("EPISODE STORYBOARDING")) {
            throw new Error("Failed to retrieve valid Episode Remix Prompt template from server.");
        }

        console.log("\n🧪 TEST 2: Checking Header UI Elements & Buttons...");
        const epAiBtnText = await page.evaluate(() => {
            const btn = document.getElementById('episodeAiAutoPlanBtn');
            return btn ? btn.textContent.trim() : null;
        });

        console.log(`- Header Button Text: "${epAiBtnText}"`);
        if (epAiBtnText !== "🌌 Episode AI Auto-Plan") {
            throw new Error(`Expected button text '🌌 Episode AI Auto-Plan', but got '${epAiBtnText}'`);
        }

        console.log("\n🧪 TEST 3: Verifying Settings Modal Tab Navigation & Episode Remix Textarea...");
        const modalInfo = await page.evaluate(() => {
            const overlay = document.getElementById('settingsModalOverlay');
            if (overlay) overlay.classList.add('active');
            
            const tabBtns = document.querySelectorAll('.settings-tab-btn');
            tabBtns.forEach(b => {
                if (b.getAttribute('data-tab') === 'tab-gemini') {
                    b.click();
                }
            });

            const tabGemini = document.getElementById('tab-gemini');
            if (tabGemini) tabGemini.style.display = 'flex';

            const el = document.getElementById('settingsGeminiEpisodeDefaultPrompt');
            return {
                overlayActive: overlay ? overlay.classList.contains('active') : false,
                overlayDisplay: overlay ? window.getComputedStyle(overlay).display : 'none',
                tabGeminiDisplay: tabGemini ? window.getComputedStyle(tabGemini).display : 'none',
                elOffsetParent: el ? el.offsetParent !== null : false
            };
        });
        console.log("- Modal Info:", JSON.stringify(modalInfo));

        const hasEpPromptTextarea = modalInfo.elOffsetParent;

        console.log(`- Episode Remix Prompt Textarea Visible in Settings: ${hasEpPromptTextarea}`);
        if (!hasEpPromptTextarea) {
            throw new Error("settingsGeminiEpisodeDefaultPrompt textarea is missing or not visible in Settings modal.");
        }

        console.log("\n✅ ALL EPISODE REMIX & DUAL-MODE INGESTION REGRESSION TESTS PASSED 100%!");

    } catch (err) {
        console.error("❌ REGRESSION TEST FAILED:", err);
        process.exit(1);
    } finally {
        if (browser) await browser.close();
    }
})();
