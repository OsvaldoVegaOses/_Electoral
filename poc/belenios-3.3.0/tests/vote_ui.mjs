// H2 browser regression test of the original booth. Synthetic credentials only.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const privateDir = path.join(root, '.runtime/private');
const state = JSON.parse(fs.readFileSync(path.join(privateDir, 'h2-state.json'), 'utf8'));
const journalFile = path.join(privateDir, 'h2-ui-journal.json');
const journal = fs.existsSync(journalFile) ? JSON.parse(fs.readFileSync(journalFile, 'utf8')) : {};
const save = () => fs.writeFileSync(journalFile, JSON.stringify(journal, null, 2));
let phase = 'launch';
let browser;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function latestOtp(mode) {
  const mail = execFileSync('docker', ['exec', `theogen-belenios33-poc-${mode}-1`, 'cat', '/home/belenios/poc-data/private/mail.txt'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  const matches = [...mail.matchAll(/^  (\d{6})\r?$/gm)];
  if (!matches.length) throw new Error('No fake OTP found');
  return matches.at(-1)[1];
}

async function vote(mode, index, selection, suffix = 'initial') {
  const id = `${mode}-${index}-${suffix}`;
  if (journal[id]?.phase === 'confirmed') return;
  if (journal[id]) throw new Error('Unresolved vote journal: reconcile before retrying');
  const election = state.elections[mode];
  const voter = election.voters[index];
  const creds = JSON.parse(fs.readFileSync(election.private_credentials_file, 'utf8'));
  const origin = `http://127.0.0.1:${election.port}`;
  const context = await browser.newContext({ locale: 'en-US', serviceWorkers: 'block' });
  await context.route('**/*', route => {
    const url = route.request().url();
    if (url.startsWith(origin + '/') || url.startsWith('data:') || url.startsWith('blob:')) return route.continue();
    return route.abort();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  journal[id] = { phase: 'starting', mode, synthetic_index: index, selection, suffix };
  save();
  let result;
  page.on('request', req => {
    if (req.method() === 'POST' && req.url() === `${origin}/api/elections/${election.uuid}/ballots`) {
      const raw = req.postData();
      journal[id].ballot_hash = crypto.createHash('sha256').update(raw).digest('base64').replace(/=+$/, '');
      journal[id].phase = 'submitted_precast';
      fs.writeFileSync(path.join(privateDir, id + '.ballot.json'), raw);
      save();
    }
  });
  page.on('response', async response => {
    if (response.url().startsWith(origin + '/api/cast-result/') && response.status() === 200) {
      const body = await response.json();
      result = body[0] === 'Ok' ? { kind: 'Ok', hash: body[1].hash, revote: body[1].revote } : { kind: 'Error', error: body[1] };
    }
  });
  try {
    phase = id + ':open-booth';
    await page.goto(`${origin}/election#${election.uuid}`);
    await page.locator('#start').click();
    phase = id + ':credential';
    await page.locator('#credential').fill(creds[voter]);
    await page.locator('.input-credential-section__button').click();
    phase = id + ':choose';
    await page.locator(`label[for="question_0__choice_${selection}"]`).click();
    await page.locator('.vote-navigation__next-button').click();
    phase = id + ':encrypt';
    await page.locator('.review-encrypt-section').getByRole('button', { name: 'Next', exact: true }).click();
    phase = id + ':authenticate';
    const input = page.locator('input[type=text]');
    await input.waitFor({ state: 'visible' });
    if (await page.locator('#username').isVisible()) {
      await page.locator('#username').fill(voter);
      await page.locator('input[type=submit]').click();
      await page.waitForFunction(() => !document.querySelector('#username'));
    }
    const otp = latestOtp(mode);
    await page.locator('input[type=text]').fill(otp);
    phase = id + ':confirm';
    await page.locator('input[type=submit]').click();
    for (let n = 0; n < 60 && !result; n++) await sleep(250);
    if (!result) throw new Error('No final cast result');
    const expected = suffix === 'revote' && mode === 'single' ? 'Error' : 'Ok';
    if (result.kind !== expected || (expected === 'Error' && result.error !== 'RevoteNotAllowed')) throw new Error('Unexpected cast result');
    if (expected === 'Ok') await page.locator('.final_step_ok').waitFor();
    journal[id] = { ...journal[id], phase: 'confirmed', result };
    save();
    console.log(JSON.stringify({ mode, synthetic_vote_number: index + 1, scenario: suffix, result: result.kind, error: result.error }));
  } catch (error) {
    journal[id].phase = 'unresolved';
    fs.writeFileSync(path.join(privateDir, 'ui-failure.txt'), phase + '\n' + error.stack);
    save();
    throw error;
  } finally {
    await context.close();
  }
}

try {
  browser = await chromium.launch({ headless: true });
  if (process.argv.includes('--first')) await vote('revote', 0, 0);
  else {
    for (const mode of ['revote', 'single']) {
      for (let index = 0; index < 10; index++) await vote(mode, index, index < 6 ? 0 : 1);
      await vote(mode, 0, 1, 'revote');
    }
  }
} catch {
  console.error('H2 browser test stopped at ' + phase + '; reconcile the private journal before retrying.');
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
}
