import { defineConfig, devices } from "@playwright/test";

// Smoke tests of the UI with the backend mocked in the browser (tests/mock.ts): no models, no database.
export default defineConfig({
  testDir: "tests",
  timeout: 30_000,
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    // Locally use the installed Edge (no download); CI installs Chromium.
    ...devices["Desktop Chrome"],
    channel: process.env.CI ? undefined : "msedge",
    locale: "en-GB", // the app picks the market from the browser language; tests start in the UK market
  },
  webServer: {
    command: "npm run build && npx next start -p 3100",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    env: { NEXTAUTH_URL: "http://127.0.0.1:3100", NEXTAUTH_SECRET: "test-secret" },
  },
});
