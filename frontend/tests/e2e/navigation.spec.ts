import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("sidebar links are visible", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Elements" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("link", { name: "Values" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Schemas" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Queue" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Runs" })).toBeVisible();
  });

  test("sidebar has section headers", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("BROWSE", { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("CURATION", { exact: true })).toBeVisible();
    await expect(page.getByText("PIPELINE", { exact: true })).toBeVisible();
  });

  test("elements page loads", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("Data Elements")).toBeVisible({ timeout: 10000 });
  });

  test("schemas page loads", async ({ page }) => {
    await page.goto("/schemas");
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

  test("activity page loads", async ({ page }) => {
    await page.goto("/activity");
    await expect(page.locator("h1")).toContainText("Activity", { timeout: 10000 });
  });

  test("element → detail → back traversal", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
    // Click first element
    await page.locator("table tbody tr a").first().click();
    await page.waitForURL(/\/elements\//, { timeout: 10000 });
    // Should be on detail page with tabs
    await expect(page.getByText("Summary")).toBeVisible({ timeout: 10000 });
    // Navigate back
    await page.getByText("Back to elements").click();
    await expect(page.getByText("Data Elements")).toBeVisible({ timeout: 10000 });
  });
});
