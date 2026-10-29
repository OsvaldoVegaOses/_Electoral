// Complete authentication after an explicit HTTP API ballot submission.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const privateDir = path.join(root, '.runtime/private');
const state = JSON.parse(fs.readFileSync(path.join(privateDir, 'h2-state.json'), 'utf8'));
const resultFile = path.join(privateDir, 'h2-api-votes.json');
const results = fs.existsSync(resultFile) ? JSON.parse(fs.readFileSync(resultFile, 'utf8')) : {};
const save = () => fs.writeFileSync(resultFile, JSON.stringify(results, null, 2));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let browser;
let phase = 'launch';
try {
  browser = await chromium.launch({ headless: true });
  for (const mode of ['revote', 'single']) {
    if (results[mode]?.phase === 'confirmed') continue;
    if (results[mode]) throw new Error('Unknown existing API attempt; reconcile manually');
    const e = state.elections[mode];
    const origin = `http://127.0.0.1:${e.port}`;
    const context = await browser.newContext({ locale: 'en-US', serviceWorkers: 'block' });
    await context.route('**/*', route => route.request().url().startsWith(origin + '/') ? route.continue() : route.abort());
    const page = await context.newPage();
    let final;
    page.on('response', async response => {
      if (response.url().startsWith(origin + '/api/cast-result/') && response.status() === 200) {
        const body = await response.json();
        final = body[0] === 'Ok' ? { kind: 'Ok', hash: body[1].hash, revote: body[1].revote } : { kind: 'Error', error: body[1] };
      }
    });
    phase = mode + ':API-precast';
    const before = await (await context.request.get(`${origin}/api/elections/${e.uuid}/last-event`)).json();
    const ballot = fs.readFileSync(e.api_ballot_file);
    results[mode] = { phase: 'submitting', before_event: before.hash, ballot_hash: crypto.createHash('sha256').update(ballot).digest('hex') };
    save();
    const response = await context.request.post(`${origin}/api/elections/${e.uuid}/ballots`, { data: ballot, headers: { 'Content-Type': 'application/json' } });
    assert.equal(response.status(), 401);
    const { state: authState } = await response.json();
    assert.equal(typeof authState, 'string');
    results[mode].phase = 'precast_authentication_pending'; save();
    phase = mode + ':API-authentication';
    await page.goto(`${origin}/actions/voter-login?state=${encodeURIComponent(authState)}`);
    await page.locator('input[type=text]').waitFor();
    if (await page.locator('#username').isVisible()) {
      await page.locator('#username').fill(e.voters[0]);
      await page.locator('input[type=submit]').click();
      await page.waitForFunction(() => !document.querySelector('#username'));
    }
    const mail = execFileSync('docker', ['exec', `theogen-belenios33-poc-${mode}-1`, 'cat', '/home/belenios/poc-data/private/mail.txt'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    const otp = [...mail.matchAll(/^  (\d{6})\r?$/gm)].at(-1)[1];
    await page.locator('input[type=text]').fill(otp);
    phase = mode + ':API-confirmation';
    await page.locator('input[type=submit]').click();
    for (let i = 0; i < 60 && !final; i++) await sleep(250);
    assert.ok(final);
    assert.equal(final.kind, mode === 'revote' ? 'Ok' : 'Error');
    if (mode === 'single') assert.equal(final.error, 'RevoteNotAllowed');
    const after = await (await context.request.get(`${origin}/api/elections/${e.uuid}/last-event`)).json();
    if (mode === 'single') assert.equal(after.hash, before.hash);
    const active = await (await context.request.get(`${origin}/api/elections/${e.uuid}/ballots`)).json();
    assert.equal(Object.keys(active).length, 10);
    assert.equal(Object.hasOwn(active, results[mode].ballot_hash), mode === 'revote');
    const duplicate = fs.readFileSync(path.join(privateDir, `${mode}-0-initial.ballot.json`));
    const dup = await context.request.post(`${origin}/api/elections/${e.uuid}/ballots`, { data: duplicate, headers: { 'Content-Type': 'application/json' } });
    assert.equal(dup.status(), 400);
    const duplicateError = (await dup.json()).error;
    assert.deepEqual(duplicateError, ['CastError', 'DuplicateBallot']);
    results[mode] = { ...results[mode], phase: 'confirmed', final, after_event: after.hash, active_ballots: 10, duplicate_status: 400, duplicate_error: duplicateError };
    save();
    await context.close();
    console.log(JSON.stringify({ mode, method: 'API plus official web authentication', final: final.kind, error: final.error, active_ballots: 10, duplicate_rejected: true }));
  }
} catch (error) {
  fs.writeFileSync(path.join(privateDir, 'api-vote-failure.txt'), phase + '\n' + error.stack);
  console.error('API vote test stopped at ' + phase + '; reconcile ignored private state before retry.');
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
}
