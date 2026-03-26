import { test, expect } from "@playwright/test";

test.describe("Element Browser", () => {
  test("loads element list with seed data", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("Data Elements")).toBeVisible();
    await expect(page.getByText("5 elements")).toBeVisible({ timeout: 15000 });
  });

  test("displays element names in table", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("5 elements")).toBeVisible({ timeout: 15000 });
    // Seed data includes "age" and "sex" elements
    await expect(page.locator("table")).toBeVisible();
    const rows = page.locator("table tbody tr");
    await expect(rows).not.toHaveCount(0);
  });

  test("click element navigates to detail page", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("5 elements")).toBeVisible({ timeout: 15000 });
    // Click first element link in the table
    const firstLink = page.locator("table tbody tr a").first();
    await firstLink.click();
    // Wait for navigation to detail page
    await page.waitForURL(/\/elements\/[a-f0-9]/, { timeout: 10000 });
    // Detail page should show "Back to elements" and "SHA-256"
    await expect(page.getByText("Back to elements")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("SHA-256")).toBeVisible();
  });

  test("element detail shows provenance and annotations", async ({ page }) => {
    // Navigate directly to the age element (seed data)
    await page.goto("/elements/a1b2c3d4e5f6");
    // Should show provenance section with source info
    await expect(page.getByText("Provenance")).toBeVisible({ timeout: 15000 });
    await expect(page.locator("text=bids").first()).toBeVisible({ timeout: 5000 });
    // Should show ontology annotations
    await expect(page.getByText("Ontology Annotations")).toBeVisible({ timeout: 5000 });
    await expect(page.locator("text=ncit").first()).toBeVisible({ timeout: 5000 });
  });

  test("has search input", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByPlaceholder("Search elements...")).toBeVisible({ timeout: 10000 });
  });

  test("has source filter dropdown", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("5 elements")).toBeVisible({ timeout: 15000 });
    const sourceSelect = page.locator("select").first();
    await expect(sourceSelect).toBeVisible();
    // Verify it has BIDS option
    const options = sourceSelect.locator("option");
    await expect(options).not.toHaveCount(0);
  });
});
