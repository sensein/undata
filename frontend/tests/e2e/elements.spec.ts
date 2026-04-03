import { test, expect } from "@playwright/test";

test.describe("Element Browser", () => {
  test("loads element list with seed data", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("Data Elements")).toBeVisible();
    // EntityDataGrid shows "N total" — wait for any count to appear
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
  });

  test("displays element names in table", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
    // Should see table rows
    await expect(page.locator("table tbody tr")).not.toHaveCount(0);
  });

  test("click element navigates to detail page", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
    // Click first EntityTag link in the table
    const firstLink = page.locator("table tbody tr a").first();
    await firstLink.click();
    await page.waitForURL(/\/elements\//, { timeout: 10000 });
    // Detail page should show tabs and back link
    await expect(page.getByText("Back to elements")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Summary")).toBeVisible();
  });

  test("element detail shows provenance", async ({ page }) => {
    // Navigate to first element via browse page (no hardcoded sha256)
    await page.goto("/elements");
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
    await page.locator("table tbody tr a").first().click();
    await page.waitForURL(/\/elements\//, { timeout: 10000 });
    // Detail page should show provenance section
    await expect(page.getByText("Sources:")).toBeVisible({ timeout: 15000 });
  });

  test("element detail has tabs", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
    await page.locator("table tbody tr a").first().click();
    await page.waitForURL(/\/elements\//, { timeout: 10000 });
    // Tab buttons for Summary, Flags, Activity
    const tabs = page.locator("button").filter({ hasText: /^(Summary|Flags|Activity)$/ });
    await expect(tabs).toHaveCount(3, { timeout: 15000 });
  });

  test("has search input", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByPlaceholder("Search elements...")).toBeVisible({ timeout: 10000 });
  });

  test("has source filter dropdown", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
    const sourceSelect = page.locator("select").first();
    await expect(sourceSelect).toBeVisible();
  });

  test("column sorting works", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText(/\d+ total/)).toBeVisible({ timeout: 15000 });
    // Click a sortable column header
    const typeHeader = page.locator("thead th").filter({ hasText: "Type" }).first();
    await typeHeader.click();
    // Should see sort indicator
    await expect(
      page.locator("thead").getByText("↑").or(page.locator("thead").getByText("↓"))
    ).toBeVisible({ timeout: 5000 });
  });
});
