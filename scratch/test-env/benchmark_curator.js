const puppeteer = require('puppeteer');

async function runPerformanceBenchmark() {
    console.log("🚀 Starting DDMA Curator Automated Performance Benchmark Suite...\n");

    const browser = await puppeteer.launch({
        headless: "new",
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    
    // Enable Metrics
    await page.evaluateOnNewDocument(() => {
        window.__perfMetrics = {};
    });

    console.log("⏱️  Measuring Initial Page Load & DOM Initialization Latency...");
    const startTime = Date.now();
    
    await page.goto('http://127.0.0.1:8000/curator.html', { waitUntil: 'networkidle0' });
    const loadDuration = Date.now() - startTime;
    
    // Wait for project data to render
    await page.waitForSelector('.clip-card', { timeout: 10000 });
    const domReadyTime = Date.now() - startTime;

    console.log(`  └─ Total Page Load Time: ${loadDuration} ms`);
    console.log(`  └─ DOM Render Time (Clips Ready): ${domReadyTime} ms`);

    // Measure DOM node count & Memory
    const metrics = await page.metrics();
    const domNodes = await page.evaluate(() => document.querySelectorAll('*').length);
    const clipCardCount = await page.evaluate(() => document.querySelectorAll('.clip-card').length);

    console.log("\n📊 Baseline Memory & DOM Node Metrics:");
    console.log(`  └─ Active Clip Cards: ${clipCardCount}`);
    console.log(`  └─ Total DOM Elements: ${domNodes}`);
    console.log(`  └─ JS Heap Used Size: ${(metrics.JSHeapUsedSize / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  └─ JS Heap Total Size: ${(metrics.JSHeapTotalSize / 1024 / 1024).toFixed(2)} MB`);

    // Measure Title Edit Input Responsiveness (10 rapid keystrokes)
    console.log("\n⚡ Measuring UI Input Responsiveness & Execution Lag...");
    const inputStart = Date.now();
    await page.focus('.clip-card-title');
    await page.keyboard.type(' Benchmark Test Title', { delay: 10 });
    const inputLag = Date.now() - inputStart;
    console.log(`  └─ 20-Keystroke Typing & Render Lag: ${inputLag} ms`);

    // Measure Collapse/Expand Toggle Performance
    const collapseStart = Date.now();
    await page.click('#collapseAllBtn');
    await page.waitForFunction(() => document.querySelectorAll('.clip-card.collapsed').length > 0);
    const collapseDuration = Date.now() - collapseStart;

    const expandStart = Date.now();
    await page.click('#expandAllBtn');
    await page.waitForFunction(() => document.querySelectorAll('.clip-card.collapsed').length === 0);
    const expandDuration = Date.now() - expandStart;

    console.log(`  └─ Collapse All Action Latency: ${collapseDuration} ms`);
    console.log(`  └─ Expand All Action Latency: ${expandDuration} ms`);

    // Measure Backend API Latency directly
    console.log("\n🌐 Measuring Backend API HTTP Latency...");
    const apiLatencies = await page.evaluate(async () => {
        const getProjStart = performance.now();
        await fetch('/get-project?id=episode_245');
        const getProjDuration = performance.now() - getProjStart;

        const savePlanStart = performance.now();
        await fetch('/save-project-plan?id=episode_245', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(window.clips || [])
        });
        const savePlanDuration = performance.now() - savePlanStart;

        return {
            getProject: Math.round(getProjDuration),
            savePlan: Math.round(savePlanDuration)
        };
    });

    console.log(`  └─ GET /get-project Latency: ${apiLatencies.getProject} ms`);
    console.log(`  └─ POST /save-project-plan Latency: ${apiLatencies.savePlan} ms`);

    console.log("\n==================================================");
    console.log("📌 BENCHMARK SUMMARY:");
    console.log(`  - DOM Render: ${domReadyTime} ms`);
    console.log(`  - Heap Usage: ${(metrics.JSHeapUsedSize / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  - Typing Lag: ${inputLag} ms`);
    console.log(`  - Collapse All: ${collapseDuration} ms`);
    console.log("==================================================\n");

    await browser.close();
}

runPerformanceBenchmark().catch(err => {
    console.error("Benchmark failed:", err);
    process.exit(1);
});
