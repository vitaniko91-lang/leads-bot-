import { test, expect } from "@playwright/test";

test("overview page loads with KPI cards", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("Leads today")).toBeVisible();
  await expect(page.getByText("Sent today")).toBeVisible();
});
