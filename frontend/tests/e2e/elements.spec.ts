import { test, expect } from "@playwright/test";

test.describe("Element Browser", () => {
  test("loads element list", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("Data Elements")).toBeVisible();
  });

  test("filters by source", async ({ page }) => {
    await page.goto("/elements");
    await page.selectOption("select", "bids");
    // Should show BIDS elements
    await expect(page.getByText("bids")).toBeVisible();
  });
});
