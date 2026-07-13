const { defineConfig, devices } = require('@playwright/test');
const path = require('path');

process.env.FONTCONFIG_FILE ||= path.join(__dirname, 'tests/browser/fontconfig.conf');

module.exports = defineConfig({
  testDir: './tests/browser',
  outputDir: 'test-results/browser',
  reporter: [['list']],
  // All projects share one ephemeral Atlas database. Serial execution keeps
  // CSRF sessions and the write workflow deterministic.
  workers: 1,
  webServer: {
    command: 'PYTHONPATH=. NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost ATLAS_E2E_PORT=18765 python tests/browser/start_atlas_server.py',
    url: 'http://localhost:18765/healthz',
    reuseExistingServer: false,
    timeout: 30000
  },
  use: {
    baseURL: process.env.ATLAS_BASE_URL || 'http://localhost:18765',
    trace: process.env.ATLAS_TRACE === '1' ? 'on' : 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  projects: [
    { name: 'chromium-1366', use: { ...devices['Desktop Chrome'], viewport: { width: 1366, height: 768 } } },
    { name: 'chromium-1920', use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } } },
    { name: 'tablet-768', use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 }, isMobile: true } }
  ]
});
