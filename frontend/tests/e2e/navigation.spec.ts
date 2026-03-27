import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("nav links are visible", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Elements" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Values" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Schemas" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Curation" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Runs" })).toBeVisible();
  });

  test("elements page loads", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("Data Elements")).toBeVisible({ timeout: 10000 });
  });

  test("schemas page loads", async ({ page }) => {
    await page.goto("/schemas");
    // Wait for heading — page uses "Schemas" as h1
    await expect(page.locator("h1")).toContainText("Schemas", { timeout: 10000 });
  });

  test("values page loads", async ({ page }) => {
    await page.goto("/values");
    await expect(page.locator("h1")).toContainText("Values", { timeout: 10000 });
  });

  test("curation page loads", async ({ page }) => {
    await page.goto("/curation");
    await expect(page.locator("h1")).toContainText("Curation", { timeout: 10000 });
  });

  test("runs page loads", async ({ page }) => {
    await page.goto("/runs");
    await expect(page.locator("h1")).toContainText("Pipeline Runs", { timeout: 10000 });
  });
});
