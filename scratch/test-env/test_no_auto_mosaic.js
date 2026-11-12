/*
test_no_auto_mosaic.js (Issue 69)

A Mosaic run must start ONLY on the user's explicit trigger (the manual
Mosaic button / /export-to-mosaic). Loading a project (GET /get-project,
which runs heal_mosaic_project_state) or reading status
(GET /get-mosaic-status) must never spawn a Mosaic pipeline.

Covers: (a) a project whose masters are all valid (episode_248), and
(b) a project with a stored mosaic_run_id but no local Mosaic file
(synthetic episode_997 fixture, created and removed by this test).
Asserts no clip reports status "running" unless the user started it,
no mosaic_jobs.json gains a running entry, and no Mosaic source file
appears on disk.
*/
const puppeteer = require('puppeteer');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

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

const DDMA = path.resolve(__dirname, '../..');
const CLIPS = path.join(DDMA, 'clips');
const RUN_IDS = {
    episode_248: [1, 2, 3, 4, 5],
    episode_249: [0, 1, 5, 6, 7, 8],
    episode_997: [0],
};

function readJobs(ep) {
    try {
        return JSON.parse(fs.readFileSync(
            path.join(DDMA, 'projects', ep, 'mosaic_jobs.json'), 'utf-8'));
    } catch (e) { return null; }
}

function mosaicFiles() {
    return new Set(fs.readdirSync(CLIPS).filter(f => f.includes('mosaic')));
}

async function runTest() {
    console.log("Starting No-Auto-Mosaic regression check...");

    // Fixture: stored run_id, no local Mosaic file, no master.
    const fixDir = path.join(DDMA, 'projects', 'episode_997');
    fs.mkdirSync(fixDir, { recursive: true });
    fs.writeFileSync(path.join(fixDir, 'project_info.json'),
        JSON.stringify({ id: 'episode_997', title: 'NoAutoMosaic' }));
    fs.writeFileSync(path.join(fixDir, 'plan.json'), JSON.stringify([
        { num: 0, title: 'T0', locked: true,
          mosaic_run_id: 'deadbeef-0000-no-autostart-ever',
          segments: [] }
    ]));

    // Snapshot files the load path is known to rewrite, to restore after.
    const snapPlan = {};
    for (const rel of ['plan.json', path.join('docs', 'plan.json')]) {
        const abs = path.join(DDMA, rel);
        snapPlan[abs] = fs.existsSync(abs) ? fs.readFileSync(abs) : null;
    }
    const snapJobs = {};
    for (const ep of Object.keys(RUN_IDS)) snapJobs[ep] = readJobs(ep);
    const filesBefore = mosaicFiles();

    const browser = await puppeteer.launch({
        executablePath: getExecutablePath(),
        headless: true,
        protocolTimeout: 120000,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);

    let failures = [];
    try {
        await page.goto('http://127.0.0.1:8000/curator.html',
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        await new Promise(r => setTimeout(r, 2000));

        const get = (url) => page.evaluate(async (u) => {
            const r = await fetch(u);
            const t = await r.text();
            let j = null;
            try { j = JSON.parse(t); } catch (e) { /* non-JSON */ }
            return { status: r.status, body: t.slice(0, 200), json: j };
        }, url);

        // Load each project (runs heal_mosaic_project_state server-side).
        for (const ep of Object.keys(RUN_IDS)) {
            const r = await get('/get-project?id=' + ep);
            console.log(`- load ${ep}: HTTP ${r.status}`);
            if (r.status !== 200) failures.push(`${ep} load HTTP ${r.status}`);
        }

        // Status reads must never report a freshly started run.
        for (const [ep, nums] of Object.entries(RUN_IDS)) {
            for (const n of nums) {
                const r = await get(`/get-mosaic-status?id=${ep}&num=${n}`);
                const st = r.json && r.json.status;
                console.log(`- status ${ep} clip ${n}: ${st} (HTTP ${r.status})`);
                if (st === 'running') {
                    failures.push(`${ep} clip ${n} reports running with no user trigger`);
                }
            }
        }

        // No running entries may appear in the persisted job stores.
        for (const ep of Object.keys(RUN_IDS)) {
            const after = readJobs(ep);
            const running = after ? Object.entries(after)
                .filter(([k, v]) => v && v.status === 'running') : [];
            console.log(`- ${ep} running jobs on disk: ${running.length}`);
            if (running.length > 0) {
                failures.push(`${ep} has running jobs on disk: ${JSON.stringify(running)}`);
            }
        }

        // Fixture must not gain a job file, and no Mosaic file may download.
        const fixJobs = path.join(fixDir, 'mosaic_jobs.json');
        if (fs.existsSync(fixJobs)) {
            failures.push('fixture gained a mosaic_jobs.json without user trigger');
        }
        const newFiles = [...mosaicFiles()].filter(f => !filesBefore.has(f));
        console.log(`- new mosaic files on disk: ${newFiles.length}`);
        if (newFiles.length > 0) {
            failures.push(`Mosaic files appeared: ${newFiles.join(', ')}`);
        }
    } finally {
        await browser.close().catch(() => {});
        // Restore files the load path rewrites; remove the fixture.
        for (const [abs, buf] of Object.entries(snapPlan)) {
            if (buf === null) { try { fs.unlinkSync(abs); } catch (e) {} }
            else fs.writeFileSync(abs, buf);
        }
        fs.rmSync(fixDir, { recursive: true, force: true });
        const docsPlan = path.join(DDMA, 'docs', 'episodes', '997', 'plan.json');
        if (fs.existsSync(docsPlan)) {
            console.log('- NOTE: docs/episodes/997/plan.json was created; removing');
            fs.rmSync(path.join(DDMA, 'docs', 'episodes', '997'),
                { recursive: true, force: true });
        }
    }

    if (failures.length > 0) {
        console.error("FAIL: " + failures.join(" | "));
        process.exit(1);
    }
    console.log("PASS: project loads and status reads started zero Mosaic pipelines.");
}

runTest().catch(e => { console.error("FAIL:", e.message); process.exit(1); });
