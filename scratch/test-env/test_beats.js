/*
test_beats.js (Phase 5, Item 2 — Beats Studio)

Beats Studio is a separate app (port 8001) wrapping the longform engine.
The Beat Studio UI moved here OUT of the cockpit podcast tab.

Covers (7 TEST blocks):
 1. beats.html loads with the studio shell (episode input, chapter strip,
    Mosaic retrigger button) and zero page errors.
 2. /api/beats/index for ep 248 returns the chapter timeline (23 chapters),
    has_video true via the hub-first master.
 3. /api/beats/beats for a Manim chapter returns beats whose preview URLs
    point at THIS server (/api/beats/beat_video) — not the cockpit paths.
 4. /api/beats/patch validates input (bad clip_num -> 400, no hang).
    A live patch is proven by hand (see report), not spent here.
 5. /api/beats/mosaic_retry forwards to the curator and the curator
    REFUSES a nonexistent clip pre-spawn (no pipeline starts). No Mosaic
    API is spent: clip 999 does not exist, the curator raises before any
    run could start.
 6. Explicit-only client gate: dismissing either confirm dialog sends
    ZERO requests to /api/beats/mosaic_retry. (The accept path is a
    manual user trigger by design and is user-tested, not auto-tested.)
 7. Static DOM: the cockpit podcast tab carries no Beat Studio UI, and
    the landing page links Beats Studio.

Requires: beats server on :8001, curator on :8000 (refusal path only).
Run: node test_beats.js  (from this directory)
*/
const puppeteer = require('puppeteer');
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

const BEATS = 'http://127.0.0.1:8001';
const INGEST_DIR = path.resolve(__dirname, '../../../ingest');

async function runTest() {
    console.log('Starting Beats Studio regression check...');
    const browser = await puppeteer.launch({
        executablePath: getExecutablePath(),
        headless: true,
        protocolTimeout: 120000,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);
    const failures = [];
    const ok = (n, cond, msg) => {
        console.log(`- TEST ${n}: ${cond ? 'PASS' : 'FAIL'} — ${msg}`);
        if (!cond) failures.push(`TEST ${n}: ${msg}`);
    };

    try {
        // TEST 1: page shell
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.goto(BEATS + '/beats.html?ep=248',
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        await new Promise(r => setTimeout(r, 4000));
        const shell = await page.evaluate(() => ({
            title: document.title,
            ep: document.getElementById('beats-ep') ? document.getElementById('beats-ep').value : null,
            strip: !!document.getElementById('lf-chapter-strip'),
            retrigger: !!document.getElementById('btn-beats-mosaic-retry'),
            chapters: document.querySelectorAll('#lf-chapter-strip button').length,
        }));
        ok(1, shell.ep === '248' && shell.strip && shell.retrigger && shell.chapters >= 20,
            `shell ep=${shell.ep} strip=${shell.strip} retrigger=${shell.retrigger} chapters=${shell.chapters} pageerrors=${errors.length}`);
        if (errors.length) failures.push('TEST 1 pageerrors: ' + errors.join('; '));

        // TEST 2 + 3: data endpoints (via page fetch, same origin)
        const idx = await page.evaluate(async () => {
            const r = await fetch('/api/beats/index?ep=248');
            return { status: r.status, j: await r.json() };
        });
        ok(2, idx.status === 200 && idx.j.chapters && idx.j.chapters.length >= 20 && idx.j.has_video === true,
            `index chapters=${idx.j.chapters && idx.j.chapters.length} has_video=${idx.j.has_video}`);
        const beats = await page.evaluate(async () => {
            const r = await fetch('/api/beats/beats?ep=248&clip_num=4');
            return { status: r.status, j: await r.json() };
        });
        const bl = (beats.j && beats.j.beats) || [];
        const badUrls = bl.filter(b => (b.beat_video_url || '').includes('/api/podcast/'));
        ok(3, beats.status === 200 && bl.length > 0 && badUrls.length === 0,
            `clip4 beats=${bl.length} cockpit-url leftovers=${badUrls.length}`);

        // TEST 4: patch validation
        const pv = await page.evaluate(async () => {
            const r = await fetch('/api/beats/patch', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ep: '248', clip_num: 'xx' })
            });
            return { status: r.status, t: await r.text() };
        });
        ok(4, pv.status === 400, `bad clip_num -> HTTP ${pv.status}`);

        // TEST 5: mosaic_retry refused pre-spawn (clip 999 does not exist)
        const mr = await page.evaluate(async () => {
            const r = await fetch('/api/beats/mosaic_retry', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ep: '248', clip_num: 999 })
            });
            return { status: r.status, t: await r.text() };
        });
        const refused = mr.status !== 200 && /not found|refus|missing|404|500/i.test(mr.t);
        ok(5, refused, `clip 999 -> HTTP ${mr.status} (${mr.t.slice(0, 90)})`);

        // TEST 6: dismissing a confirm sends zero mosaic_retry requests
        let retryHits = 0;
        await page.setRequestInterception(true);
        const handler = req => {
            if (req.url().includes('/api/beats/mosaic_retry')) retryHits++;
            req.continue();
        };
        page.on('request', handler);
        page.on('dialog', async d => { await d.dismiss(); });
        await page.evaluate(() => { beatsMosaicRetrigger(); });
        await new Promise(r => setTimeout(r, 1500));
        page.off('request', handler);
        await page.setRequestInterception(false);
        ok(6, retryHits === 0, `dismissed confirms -> mosaic_retry requests=${retryHits}`);

        // TEST 7: static DOM — cockpit clean, landing linked
        const cock = await page.goto('file:///' + path.join(INGEST_DIR, 'cockpit.html').replace(/\\/g, '/'),
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        const remnants = await page.evaluate(() => ([
            'btn-submode-longform', 'submode-view-longform', 'btn-top-beat-studio'
        ].map(id => document.getElementById(id)).filter(Boolean).length));
        const land = await page.goto('file:///' + path.join(INGEST_DIR, 'landing.html').replace(/\\/g, '/'),
            { waitUntil: 'domcontentloaded', timeout: 30000 });
        const linked = await page.evaluate(() =>
            !!document.querySelector('button[onclick="launchBeats()"]'));
        ok(7, cock && remnants === 0 && land && linked,
            `cockpit longform remnants=${remnants} landing launchBeats=${linked}`);
    } finally {
        await browser.close().catch(() => {});
    }

    if (failures.length > 0) {
        console.error('FAIL: ' + failures.join(' | '));
        process.exit(1);
    }
    console.log('PASS: Beats Studio 7/7.');
}

runTest().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
