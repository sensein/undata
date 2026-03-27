import { test, expect } from "@playwright/test";

test("homepage loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "undata" })).toBeVisible();
});

test("elements page loads with search input", async ({ page }) => {
  await page.goto("/elements");
  await expect(page.getByPlaceholder("Search elements...")).toBeVisible({ timeout: 10000 });
});
