import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.HYS_E2E_BASE_URL ?? "https://localhost";
const base = new URL(baseURL);
const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(base.hostname);
if (!loopback || process.env.HYS_E2E_ALLOW_SYNTHETIC_MUTATIONS !== "1") {
  throw new Error(
    "Browser journeys require loopback and explicit synthetic mutation opt-in.",
  );
}

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: "list",
  use: {
    baseURL,
    ignoreHTTPSErrors: process.env.HYS_E2E_ALLOW_LOCAL_TLS === "1",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"], defaultBrowserType: "chromium" },
    },
  ],
});
