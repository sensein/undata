import { test, expect } from "@playwright/test";

test.describe("Curation Queue", () => {
  test("loads curation page", async ({ page }) => {
    await page.goto("/curation");
    await expect(page.getByText("Curation Queue")).toBeVisible();
  });
});
