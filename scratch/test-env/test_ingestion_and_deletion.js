const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

async function runTest() {
    console.log("🚀 Starting Comprehensive Project Creation & Deletion Regression Test...");
    const browser = await puppeteer.launch({
        headless: true,
        args: [
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

    const testEpNum = 999;
    const testProjId = `episode_${testEpNum}`;
    const testProjDir = path.join('projects', testProjId);
    const testDocsDir = path.join('docs', 'episodes', `${testEpNum}`);

    try {
        console.log("Navigating to http://127.0.0.1:8000/curator.html ...");
        await page.goto('http://127.0.0.1:8000/curator.html', { waitUntil: 'domcontentloaded', timeout: 10000 });
        await new Promise(r => setTimeout(r, 2000));

        // 🧪 TEST 1: Project Creation via API / UI Workflow
        console.log(`\n🧪 TEST 1: Simulating Project Creation for Episode ${testEpNum}...`);
        
        // Ensure test dirs are clean before starting
        if (fs.existsSync(testProjDir)) fs.rmSync(testProjDir, { recursive: true, force: true });
        if (fs.existsSync(testDocsDir)) fs.rmSync(testDocsDir, { recursive: true, force: true });

        const createRes = await page.evaluate(async (epNum) => {
            const res = await fetch('/create-project', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: `Episode ${epNum}`,
                    title: `Episode ${epNum} Test Project`,
                    audio_source: "title-card-music.mp3"
                })
            });
            return await res.json();
        }, testEpNum);

        console.log(`- Create Project API Result:`, createRes);
        if (!createRes.success) {
            throw new Error(`FAIL: Project creation API failed: ${createRes.error || 'Unknown error'}`);
        }

        // Verify project directory structure on disk
        const projInfoPath = path.join(testProjDir, 'project_info.json');
        const planPath = path.join(testProjDir, 'plan.json');

        console.log(`- Verifying project_info.json exists: ${fs.existsSync(projInfoPath)}`);
        console.log(`- Verifying plan.json exists: ${fs.existsSync(planPath)}`);

        if (!fs.existsSync(projInfoPath) || !fs.existsSync(planPath)) {
            throw new Error("FAIL: Created project files (project_info.json / plan.json) missing from disk!");
        }

        // Verify docs/episodes.json manifest contains Episode 999
        const manifestPath = path.join('docs', 'episodes.json');
        const manifestData = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
        const hasTestEpInManifest = manifestData.some(e => String(e.id) === String(testEpNum));
        console.log(`- Verifying docs/episodes.json manifest contains Episode ${testEpNum}: ${hasTestEpInManifest}`);

        if (!hasTestEpInManifest) {
            throw new Error(`FAIL: Episode ${testEpNum} was not registered in docs/episodes.json!`);
        }

        // 🧪 TEST 2: Project Deletion & Clean Manifest Pruning
        console.log(`\n🧪 TEST 2: Testing Project Deletion & Clean Manifest Pruning for Episode ${testEpNum}...`);
        
        const deleteRes = await page.evaluate(async (projId) => {
            const res = await fetch('/delete-project', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_id: projId })
            });
            return await res.json();
        }, testProjId);

        console.log(`- Delete Project API Result:`, deleteRes);
        if (!deleteRes.success) {
            throw new Error(`FAIL: Delete project API failed: ${deleteRes.error || 'Unknown error'}`);
        }

        // Verify project directory removed from disk
        const isProjDirDeleted = !fs.existsSync(testProjDir);
        const isDocsDirDeleted = !fs.existsSync(testDocsDir);
        console.log(`- Verifying project directory deleted: ${isProjDirDeleted}`);
        console.log(`- Verifying docs episode directory deleted: ${isDocsDirDeleted}`);

        if (!isProjDirDeleted) {
            throw new Error(`FAIL: Project directory ${testProjDir} was not deleted!`);
        }

        // Verify manifest updated without orphan entries
        const updatedManifestData = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
        const isTestEpInUpdatedManifest = updatedManifestData.some(e => String(e.id) === String(testEpNum));
        console.log(`- Verifying Episode ${testEpNum} removed from manifest: ${!isTestEpInUpdatedManifest}`);

        if (isTestEpInUpdatedManifest) {
            throw new Error(`FAIL: Episode ${testEpNum} remained in docs/episodes.json after deletion!`);
        }

        if (capturedErrors.length > 0) {
            throw new Error(`FAIL: Captured ${capturedErrors.length} unhandled browser error(s):\n` + capturedErrors.join('\n'));
        }

        console.log("\n✅ ALL PROJECT CREATION & DELETION REGRESSION TESTS PASSED 100%!");

    } catch (err) {
        console.error("\n❌ TEST FAILURE DETECTED:");
        console.error(err.message);
        process.exit(1);
    } finally {
        // Clean up any remaining test files
        if (fs.existsSync(testProjDir)) fs.rmSync(testProjDir, { recursive: true, force: true });
        if (fs.existsSync(testDocsDir)) fs.rmSync(testDocsDir, { recursive: true, force: true });
        await browser.close();
    }
}

runTest();
