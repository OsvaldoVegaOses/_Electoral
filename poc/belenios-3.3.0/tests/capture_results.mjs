import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const docs = path.resolve(root, '../../doc/poc-belenios/evidencias');
const report = JSON.parse(fs.readFileSync(path.join(docs, 'h2-resultados.json'), 'utf8'));
const browser = await chromium.launch({ headless: true });
try {
  for (const [mode, election] of Object.entries(report.elections)) {
    const base = mode === 'revote' ? 'http://127.0.0.1:18001' : 'http://127.0.0.1:18002';
    const context = await browser.newContext({ locale: 'en-US', viewport: { width: 1280, height: 960 }, serviceWorkers: 'block' });
    await context.route('**/*', route => route.request().url().startsWith(base + '/') ? route.continue() : route.abort());
    const page = await context.newPage();
    await page.goto(`${base}/election#${election.uuid}`);
    await page.getByText('This election has been tallied.', { exact: true }).waitFor();
    await page.getByText('Lista A', { exact: true }).waitFor();
    await page.getByText('Lista B', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(docs, `h2-${mode}-resultado.png`), fullPage: true });
    await context.close();
    console.log(mode + ': public result screenshot captured');
  }
} finally { await browser.close(); }
