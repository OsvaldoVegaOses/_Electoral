import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['junit', { outputFile: 'test-results/junit.xml' }]],
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || './test-results',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'off',
    screenshot: 'off',
  },
  webServer: [
    {
      command: `python -m uvicorn main:app --host 127.0.0.1 --port ${process.env.S3_API_PORT || 8000}`,
      cwd: '../backend',
      url: `${process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000'}/api/health`,
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${process.env.S3_UI_PORT || 5173} --strictPort`,
      url: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 120000,
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
