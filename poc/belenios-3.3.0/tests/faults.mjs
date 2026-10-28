import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const privateDir = path.join(root, '.runtime/private');
const fixture = JSON.parse(fs.readFileSync(path.join(privateDir, 'faults.json'), 'utf8'));
const reportPath = path.resolve(root, '../../doc/poc-belenios/evidencias/h2-fallos.json');
if (fs.existsSync(reportPath)) throw new Error('Fault test already recorded: no automatic repeated mutation');
const origin = 'http://127.0.0.1:18001';
const base = `${origin}/api/elections/${fixture.uuid}`;
const checks = [];
const browser = await chromium.launch({ headless: true });
let phase = 'start';
const context = await browser.newContext({ locale: 'en-US', serviceWorkers: 'block' });
await context.route('**/*', r => r.request().url().startsWith(origin + '/') ? r.continue() : r.abort());
const record = (check, observed) => checks.push({ check, observed, passed: true });
const count = async () => Object.keys(await (await context.request.get(base + '/ballots')).json()).length;
const post = async raw => context.request.post(base + '/ballots', { data: raw, headers: { 'Content-Type': 'application/json' } });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const otp = () => [...execFileSync('docker', ['exec', 'theogen-belenios33-poc-revote-1', 'cat', '/home/belenios/poc-data/private/mail.txt'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).matchAll(/^  (\d{6})\r?$/gm)].at(-1)[1];

async function login(state, refresh = false) {
  const page = await context.newPage();
  await page.goto(`${origin}/actions/voter-login?state=${encodeURIComponent(state)}`);
  await page.locator('input[type=text]').waitFor();
  if (await page.locator('#username').isVisible()) {
    await page.locator('#username').fill('aux01@ejemplo.test');
    await page.locator('input[type=submit]').click();
    await page.waitForFunction(() => !document.querySelector('#username'));
  }
  if (refresh) { await page.reload(); await page.locator('input[type=text]').waitFor(); }
  return page;
}

try {
  phase = 'incorrect-credential';
  const wrong = JSON.parse(fs.readFileSync(fixture.ballots[0], 'utf8'));
  wrong.credential = 'not-a-valid-group-element';
  const invalid = await post(JSON.stringify(wrong)); assert.equal(invalid.status(), 400); assert.equal(await count(), 0);
  record('incorrect_credential', { http: 400, active_ballots: 0 });
  phase = 'close-browser-before-confirmation';
  const pre = await post(fs.readFileSync(fixture.ballots[0])); assert.equal(pre.status(), 401);
  const oldState = (await pre.json()).state;
  const abandoned = await login(oldState); await abandoned.close(); assert.equal(await count(), 0);
  record('browser_closed_before_confirmation', { active_ballots: 0 });
  phase = 'session-lost-on-restart';
  execFileSync('docker', ['compose', '-f', path.join(root, 'docker-compose.poc.yml'), 'restart', 'revote'], { stdio: ['ignore', 'pipe', 'pipe'] });
  for (let i = 0; i < 45; i++) {
    try { const r = await context.request.get(origin + '/api/configuration', { timeout: 2000 }); if (r.status() === 200) break; } catch {}
    await sleep(1000);
  }
  const lost = await context.request.get(`${origin}/api/cast-result/${oldState}`); assert.equal(lost.status(), 404); assert.equal(await count(), 0);
  record('voter_authentication_state_lost_on_restart', { http: 404, active_ballots: 0 });
  phase = 'refresh-and-confirm';
  const fresh = await post(fs.readFileSync(fixture.ballots[1])); assert.equal(fresh.status(), 401);
  const freshState = (await fresh.json()).state;
  const page = await login(freshState, true);
  await page.locator('input[type=text]').fill(otp()); await page.locator('input[type=submit]').click();
  for (let i = 0; i < 60 && await count() === 0; i++) await sleep(250);
  assert.equal(await count(), 1); await page.close();
  record('refresh_during_authentication', { accepted_after_confirmation: 1 });
  const duplicate = await post(fs.readFileSync(fixture.ballots[1])); assert.equal(duplicate.status(), 400);
  record('double_submit', { http: 400, active_ballots: await count() });
  phase = 'closed-election';
  const token = (await (await context.request.post(origin + '/api/login/demo', { data: { username: 'poc-admin' } })).json()).token;
  const closed = await context.request.post(base, { data: '"Close"', headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' } }); assert.equal(closed.status(), 200);
  const closedPre = await post(fs.readFileSync(fixture.ballots[2])); assert.equal(closedPre.status(), 401);
  const closedState = (await closedPre.json()).state;
  const closedPage = await login(closedState); await closedPage.locator('input[type=text]').fill(otp()); await closedPage.locator('input[type=submit]').click();
  let final;
  for (let i = 0; i < 60; i++) {
    const r = await context.request.get(`${origin}/api/cast-result/${closedState}`);
    if (r.status() === 200) { final = await r.json(); break; } await sleep(250);
  }
  assert.deepEqual(final, ['Error', 'ElectionClosed']); assert.equal(await count(), 1);
  record('closed_election_backend_rejection', { error: 'ElectionClosed', active_ballots: 1 });
  await closedPage.close();
  phase = 'addressless-voter-draft';
  // Inspect the supported input contract without adding a person to the frozen election.
  const account = await (await context.request.get(origin + '/api/account', { headers: { Authorization: 'Bearer ' + token } })).json();
  const draft = { version: 1, owners: [account.id], booth: 2, group: 'Ed25519', languages: ['en'], authentication: ['Configured', 'email'], questions: { name: 'Contrato sin correo', description: 'No se abre ni se vota', administrator: 'Ficticio', credential_authority: 'externa', questions: [{ question: 'Q', answers: ['A', 'B'], min: 1, max: 1 }] } };
  const created = await context.request.post(origin + '/api/elections', { data: draft, headers: { Authorization: 'Bearer ' + token } }); assert.equal(created.status(), 200);
  const noMailId = await created.json();
  const noMail = await context.request.put(`${origin}/api/elections/${noMailId}/draft/voters`, { data: [{ login: 'unidad-sin-correo' }], headers: { Authorization: 'Bearer ' + token } }); assert.equal(noMail.status(), 200);
  record('addressless_identity_input_contract', { http: 200, limitation: 'Accepted in draft; real email/OTP delivery is not demonstrated. Draft remains unopened.' });
  fs.writeFileSync(reportPath, JSON.stringify({ fixture: 'auxiliary weak synthetic fixture, separate from the two threshold elections', uuid: fixture.uuid, checks, limitation: 'Restart expiry tested; 900-second natural timeout and full addressless-voter delivery remain untested.' }, null, 2));
  console.log(JSON.stringify({ H2_additional_fault_checks: checks.length, passed: true }));
} catch (error) {
  fs.writeFileSync(path.join(privateDir, 'fault-test-failure.txt'), phase + '\n' + error.stack);
  console.error('Fault tests stopped at ' + phase + '; no automatic repeated vote.'); process.exitCode = 1;
} finally { await context.close(); await browser.close(); }
