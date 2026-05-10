import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./src/tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    httpCredentials: { username: "admin", password: "change-me-please" },
  },
});
