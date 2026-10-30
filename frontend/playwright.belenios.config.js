import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e-belenios', testMatch: '**/*.spec.js', workers: 1, retries: 0, forbidOnly: true,
  outputDir: '../.runtime/belenios-ui',
  reporter: [['list'], ['junit', { outputFile: '../.runtime/belenios-ui-junit.xml' }]],
  use: { baseURL: 'http://127.0.0.1:5174', ...devices['Desktop Chrome'], screenshot: 'only-on-failure' },
  webServer: { command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort', url: 'http://127.0.0.1:5174', reuseExistingServer: false },
});
