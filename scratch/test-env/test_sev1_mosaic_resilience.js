/**
 * SEVERITY 1 REGRESSION TEST SUITE: Mosaic State Preservation & Pipeline Resilience
 * 
 * Tests:
 * 1. Source audio dependency resolution & baseline draft MP4 compilation.
 * 2. Directory auto-creation safety (ensures no FileNotFoundError crashes).
 * 3. State non-destruction guard (verifies completed mosaic_run_ids are NEVER deleted on transient errors).
 * 4. UI visual verification in Puppeteer (verifies completed clips 1-8 are green with ZERO "Failed" states).
 */

const puppeteer = require('puppeteer');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

async function runSev1MosaicTestSuite() {
    console.log("=========================================================================");
    console.log("🛡️  SEVERITY 1 REGRESSION SUITE: Mosaic Resilience & State Preservation");
    console.log("=========================================================================");

    const rootDir = path.resolve(__dirname, '../../');
    const projectDir = path.join(rootDir, 'projects', 'episode_246');
    const planPath = path.join(projectDir, 'plan.json');
    const mosaicJobsPath = path.join(projectDir, 'mosaic_jobs.json');

    // 🧪 TEST 1: Source Audio Dependency Verification
    console.log("\n🧪 TEST S1-1: Verifying Source Audio & Slicing Pipeline...");
    const audioPath = path.join(projectDir, '246.m4a');
    if (!fs.existsSync(audioPath)) {
        throw new Error(`FAIL: Source audio file missing at ${audioPath}`);
    }
    console.log(`- Source audio present: ${audioPath} (${(fs.statSync(audioPath).size / 1024 / 1024).toFixed(2)} MB)`);

    const cutOutput = execSync(`python ddma.py cut --audio projects/episode_246/246.m4a --plan-file projects/episode_246/plan.json --out-dir clips`, { cwd: rootDir }).toString();
    console.log("- ddma.py cut executed successfully without missing audio errors.");

    // 🧪 TEST 2: Baseline Draft MP4 Compilation for Clip 9
    console.log("\n🧪 TEST S1-2: Verifying Baseline 740x740 Draft Compilation for Clip 9...");
    const compOutput = execSync(`python ddma.py compile-clip --num 9 --plan-file projects/episode_246/plan.json --force-draft`, { cwd: rootDir }).toString();
    const clip9Draft = path.join(rootDir, 'clips', '246-9.mp4');
    if (!fs.existsSync(clip9Draft) || fs.statSync(clip9Draft).size < 100000) {
        throw new Error(`FAIL: Baseline draft video for Clip 9 was not generated!`);
    }
    console.log(`- Baseline draft compiled: ${clip9Draft} (${(fs.statSync(clip9Draft).size / 1024 / 1024).toFixed(2)} MB)`);

    // 🧪 TEST 3: State Non-Destruction Verification
    console.log("\n🧪 TEST S1-3: Verifying mosaic_run_id Preservation in plan.json...");
    const planData = JSON.parse(fs.readFileSync(planPath, 'utf-8'));
    const mosaicJobsData = JSON.parse(fs.readFileSync(mosaicJobsPath, 'utf-8'));

    for (let num = 1; num <= 8; num++) {
        const clip = planData.find(c => c.num === num);
        const job = mosaicJobsData[String(num)];
        if (!clip || !clip.mosaic_run_id) {
            throw new Error(`FAIL: Clip ${num} has missing or deleted mosaic_run_id in plan.json!`);
        }
        if (!job || job.status !== 'completed') {
            throw new Error(`FAIL: Clip ${num} in mosaic_jobs.json has status '${job ? job.status : 'undefined'}' instead of 'completed'!`);
        }
    }
    console.log("- Verified Clips 1-8 all retain valid, non-null mosaic_run_ids in plan.json.");
    console.log("- Verified Clips 1-8 all retain 'completed' status in mosaic_jobs.json.");

    // 🧪 TEST 4: Puppeteer Browser UI Visual Inspection
    console.log("\n🧪 TEST S1-4: Running Headless Browser UI Visual State Verification...");
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();
        await page.setViewport({ width: 1400, height: 900 });

        console.log("Navigating to http://127.0.0.1:8000/curator.html?project=episode_246 ...");
        await page.goto('http://127.0.0.1:8000/curator.html?project=episode_246', { waitUntil: 'networkidle2' });
        await page.waitForFunction(() => document.querySelectorAll('.clip-card').length > 0, { timeout: 15000 });
        await new Promise(r => setTimeout(r, 1200));

        const uiEvaluation = await page.evaluate(() => {
            const cards = document.querySelectorAll('.clip-card');
            const results = [];
            let failedCount = 0;

            cards.forEach((card, idx) => {
                const clipNum = idx + 1;
                const mosaicBtn = card.querySelector('.btn-card-mosaic');
                const btnText = mosaicBtn ? mosaicBtn.textContent.trim() : 'N/A';
                const isSuccess = mosaicBtn ? mosaicBtn.classList.contains('btn-status-success') : false;
                const isFailed = mosaicBtn ? (mosaicBtn.classList.contains('btn-status-warning') || btnText.includes('Failed')) : false;
                
                if (isFailed) failedCount++;
                results.push({ clipNum, btnText, isSuccess, isFailed });
            });

            return { results, failedCount };
        });

        console.log(`- Total Evaluated Clip Cards: ${uiEvaluation.results.length}`);
        console.log(`- Total 'Failed' Buttons Found: ${uiEvaluation.failedCount} (Expected: 0)`);

        for (let i = 0; i < 8; i++) {
            const r = uiEvaluation.results[i];
            console.log(`  Clip ${r.clipNum}: Button Text = "${r.btnText}" | Green Success State = ${r.isSuccess}`);
            if (r.isFailed || !r.isSuccess) {
                throw new Error(`FAIL: Clip ${r.clipNum} displayed failure/inactive state in UI instead of completed Green state!`);
            }
        }

        if (uiEvaluation.failedCount > 0) {
            throw new Error(`FAIL: Detected ${uiEvaluation.failedCount} clip cards stuck in 'Failed' state!`);
        }

        // 🧪 TEST 5: Verify Clip 9 Mosaic Prompt Interaction
        console.log("\n🧪 TEST S1-5: Verifying Clip 9 Mosaic Prompt Opening & Content...");
        
        await page.evaluate(async () => {
            localStorage.setItem('ddma-mosaic-api-key', 'mk_xReRSluc5ttoo8j426VvJAibCxyPr4-K');
            localStorage.setItem('ddma-mosaic-agent-id', '674ba8d3-bf72-475f-9a0a-e34464d81a5b');
            if (clips[8]) {
                clips[8].locked = true;
                renderClips();
            }
            const btn = document.querySelector('.clip-card[data-index="8"] .btn-card-mosaic');
            exportToMosaic(8, btn, true);
        });

        await page.waitForFunction(() => {
            const overlay = document.getElementById('mosaicPromptModalOverlay');
            const textarea = document.getElementById('mosaicPromptTextarea');
            return overlay && overlay.classList.contains('active') && textarea && textarea.value.length > 50;
        }, { timeout: 15000 });
        
        const modalEvaluation = await page.evaluate(() => {
            const overlay = document.getElementById('mosaicPromptModalOverlay');
            const textarea = document.getElementById('mosaicPromptTextarea');
            return {
                modalActive: overlay && overlay.classList.contains('active'),
                promptText: textarea ? textarea.value : ''
            };
        });

        console.log(`- Mosaic Prompt Modal Opened: ${modalEvaluation.modalActive}`);
        console.log(`- Prompt contains Spoken Script Context: ${modalEvaluation.promptText.includes('DYNAMIC CLIP CONTEXT')}`);
        
        if (!modalEvaluation.modalActive || !modalEvaluation.promptText.includes('DYNAMIC CLIP CONTEXT')) {
            throw new Error("FAIL: Mosaic Prompt modal failed to populate with dynamic clip context!");
        }

        // Close modal
        await page.click('#closeMosaicPromptModalBtn');
        await new Promise(r => setTimeout(r, 400));

        console.log("\n=========================================================================");
        console.log("🎉 ALL SEVERITY 1 REGRESSION TESTS PASSED! ZERO FAILURES DETECTED.");
        console.log("=========================================================================");

    } finally {
        await browser.close();
    }
}

runSev1MosaicTestSuite().catch(err => {
    console.error("\n❌ SEVERITY 1 TEST FAILURE DETECTED:");
    console.error(err.message);
    process.exit(1);
});
