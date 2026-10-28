import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e-belenios', testMatch: 'belenios.spec.js', workers: 1, retries: 0,
  outputDir: '../.runtime/belenios-ui', reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5174', ...devices['Desktop Chrome'], screenshot: 'only-on-failure' },
  webServer: { command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort', url: 'http://127.0.0.1:5174', reuseExistingServer: false },
});
