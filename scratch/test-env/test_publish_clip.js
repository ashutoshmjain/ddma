/*
test_publish_clip.js (Issue 80 — per-clip Publish)

The Publish button is locked-gated like the Mosaic button: unlocked clips get
a greyed disabled button and POST /publish-clip returns 403 without touching
git. Locked clips get an enabled button that POSTs to /publish-clip.

Covers (6 TEST blocks, no git push spent anywhere):
 1. POST /publish-clip for an UNLOCKED fixture clip -> HTTP 403, and HEAD
    is unchanged (no commit happened).
 2. Fixture project page renders the Publish button greyed/disabled.
 3. Locked 249-10's card renders an ENABLED Publish button whose click
    fires POST /publish-clip (request intercepted + aborted, so no push).
 4. Idempotent re-publish of the already-live 249-10 succeeds with
    already_published=true and no new commit.
 5. Re-publish of already-live 249-11 returns persisted=true and lands
    published=true + published_url on the hub plan clip (ITEM 11).
 6. Fresh page load renders 249-11 as green "Published", a locked
    unpublished clip as enabled "Publish", unlocked clips greyed (ITEM 11).

Requires: curator on :8000. Run: node test_publish_clip.js (from this dir)
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
const DEEPDIVE = path.resolve(DDMA, '..');

async function runTest() {
    console.log('Starting Publish-button regression check...');

    // Fixture: unlocked clip, no segments (publish must refuse before any work).
    const fixDir = path.join(DDMA, 'projects', 'episode_997');
    fs.mkdirSync(fixDir, { recursive: true });
    fs.writeFileSync(path.join(fixDir, 'project_info.json'),
        JSON.stringify({ id: 'episode_997', title: 'PublishGate' }));
    fs.writeFileSync(path.join(fixDir, 'plan.json'), JSON.stringify([
        { num: 0, title: 'T0', locked: false, segments: [] }
    ]));

    const headBefore = execSync('git rev-parse HEAD', { cwd: DEEPDIVE }).toString().trim();
    const failures = [];
    const ok = (n, cond, msg) => {
        console.log(`- TEST ${n}: ${cond ? 'PASS' : 'FAIL'} — ${msg}`);
        if (!cond) failures.push(`TEST ${n}: ${msg}`);
    };

    const browser = await puppeteer.launch({
        executablePath: getExecutablePath(),
        headless: true,
        protocolTimeout: 120000,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);

    try {
        await page.goto('http://127.0.0.1:8000/curator.html?project=episode_997',
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        await new Promise(r => setTimeout(r, 8000));

        // TEST 1: unlocked -> 403, no commit.
        const r403 = await page.evaluate(async () => {
            const r = await fetch('/publish-clip?id=episode_997&num=0', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            return { status: r.status, t: await r.text() };
        });
        const headAfter403 = execSync('git rev-parse HEAD', { cwd: DEEPDIVE }).toString().trim();
        ok(1, r403.status === 403 && headAfter403 === headBefore,
            `unlocked POST -> HTTP ${r403.status}, HEAD unchanged=${headAfter403 === headBefore}`);

        // TEST 2: fixture page renders greyed Publish.
        const grey = await page.evaluate(() => {
            const dis = [...document.querySelectorAll('button[disabled]')]
                .filter(b => (b.title || '').includes('Lock clip first to enable Publish'));
            return {
                enabled: document.querySelectorAll('[id^="publishCardBtn_"]').length,
                greyed: dis.length
            };
        });
        ok(2, grey.enabled === 0 && grey.greyed > 0,
            `enabled publish buttons=${grey.enabled} greyed publish buttons=${grey.greyed}`);

        // TEST 3: locked 249-10 renders enabled Publish; click fires the POST (aborted).
        await page.setRequestInterception(true);
        let publishHits = 0;
        const handler = req => {
            if (req.url().includes('/publish-clip')) { publishHits++; req.abort(); }
            else req.continue();
        };
        page.on('request', handler);
        await page.goto('http://127.0.0.1:8000/curator.html?project=episode_249',
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        try {
            await page.waitForFunction(
                () => [...document.querySelectorAll('[id^="publishCardBtn_"]')].length > 0,
                { timeout: 120000 });
        } catch (e) {
            ok(3, false, 'no enabled Publish button rendered for episode_249 within 120s');
            throw new Error('stop');
        }
        const btnIds = await page.evaluate(() =>
            [...document.querySelectorAll('[id^="publishCardBtn_"]')].map(b => b.id));
        await page.evaluate(() => {
            const btns = [...document.querySelectorAll('[id^="publishCardBtn_"]')];
            if (btns[0]) btns[0].click();
        });
        await new Promise(r => setTimeout(r, 3000));
        ok(3, btnIds.length > 0 && publishHits > 0,
            `enabled buttons=${btnIds.length} publish POST fired=${publishHits}`);

        // TEST 4: idempotent re-publish of the already-live clip succeeds without a new commit.
        page.off('request', handler);
        await page.setRequestInterception(false).catch(() => {});
        await page.goto('http://127.0.0.1:8000/curator.html',
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        await new Promise(r => setTimeout(r, 3000));
        const repub = await page.evaluate(async () => {
            const r = await fetch('/publish-clip?id=episode_249&num=10', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            return { status: r.status, j: await r.json() };
        });
        const headAfterRepub = execSync('git rev-parse HEAD', { cwd: DEEPDIVE }).toString().trim();
        ok(4, repub.status === 200 && repub.j.success === true && repub.j.already_published === true && headAfterRepub === headBefore,
            `re-publish -> HTTP ${repub.status} already_published=${repub.j.already_published} HEAD unchanged=${headAfterRepub === headBefore}`);

        // TEST 5 (ITEM 11): already-published re-publish persists the flag + persisted:true.
        const repub11 = await page.evaluate(async () => {
            const r = await fetch('/publish-clip?id=episode_249&num=11', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            return { status: r.status, j: await r.json() };
        });
        const hubPlan = JSON.parse(fs.readFileSync(
            'G:/My Drive/dd_hub/episodes/249/plan.json', 'utf8'));
        const hub11 = hubPlan.find(c => Number(c.num) === 11) || {};
        ok(5, repub11.status === 200 && repub11.j.success === true
            && repub11.j.already_published === true && repub11.j.persisted === true
            && hub11.published === true
            && hub11.published_url === repub11.j.url,
            `re-publish 249-11 -> already_published=${repub11.j.already_published} persisted=${repub11.j.persisted} hub flag=${hub11.published}`);

        // TEST 6 (ITEM 11): card render reads the persisted flag after a fresh load.
        await page.goto('http://127.0.0.1:8000/curator.html?project=episode_249',
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForFunction(
            () => [...document.querySelectorAll('[id^="publishCardBtn_"]')].length > 0,
            { timeout: 120000 });
        await new Promise(r => setTimeout(r, 2000));
        const render = await page.evaluate(() => {
            const byNum = {};
            document.querySelectorAll('[id^="publishCardBtn_"]').forEach(b => {
                const card = b.closest('.clip-card');
                const badge = card ? card.querySelector('.clip-num-badge') : null;
                const num = badge ? badge.textContent.trim() : b.id;
                byNum[num] = { text: (b.textContent || '').trim(), cls: b.className, disabled: !!b.disabled };
            });
            const greyed = [...document.querySelectorAll('button[disabled]')]
                .filter(b => (b.title || '').includes('Lock clip first to enable Publish')).length;
            return { byNum, greyed };
        });
        const pubBtn = render.byNum['249-11'] || {};
        const lockedUnpub = Object.entries(render.byNum)
            .find(([num, b]) => {
                const hc = hubPlan.find(c => `249-${c.num}` === num) || {};
                return hc.locked && !hc.published;
            });
        const unlocked = Object.entries(render.byNum)
            .find(([num, b]) => {
                const hc = hubPlan.find(c => `249-${c.num}` === num) || {};
                return !hc.locked;
            });
        ok(6, pubBtn.text === '✅ Published' && pubBtn.cls.includes('btn-status-success') && !pubBtn.disabled,
            `249-11 renders '${pubBtn.text}' green after reload`);
        ok(6.1, !!lockedUnpub && lockedUnpub[1].text === '🚀 Publish' && !lockedUnpub[1].disabled,
            `locked unpublished ${lockedUnpub ? lockedUnpub[0] : '?'} renders enabled Publish`);
        ok(6.2, render.greyed > 0,
            `unlocked clips still greyed (greyed publish buttons=${render.greyed})`);
    } catch (e) {
        if (e.message !== 'stop') throw e;
    } finally {
        await browser.close().catch(() => {});
        fs.rmSync(fixDir, { recursive: true, force: true });
    }

    const headAfter = execSync('git rev-parse HEAD', { cwd: DEEPDIVE }).toString().trim();
    if (headAfter !== headBefore) failures.push(`HEAD moved ${headBefore} -> ${headAfter} (test must not push)`);
    else console.log('- HEAD unchanged (no test push): PASS');

    if (failures.length > 0) {
        console.error('FAIL: ' + failures.join(' | '));
        process.exit(1);
    }
    console.log('PASS: Publish gating 6/6.');
}

runTest().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
