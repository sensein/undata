import { test, expect } from "@playwright/test";

test.describe("Element Browser", () => {
  test("loads element list with seed data", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("Data Elements")).toBeVisible();
    // EntityDataGrid shows "N total" — seed has 5 elements
    await expect(page.getByText("5 total")).toBeVisible({ timeout: 15000 });
  });

  test("displays element names in table", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("5 total")).toBeVisible({ timeout: 15000 });
    // Should see table rows
    await expect(page.locator("table tbody tr")).not.toHaveCount(0);
  });

  test("click element navigates to detail page", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("5 total")).toBeVisible({ timeout: 15000 });
    // Click first EntityTag link in the table
    const firstLink = page.locator("table tbody tr a").first();
    await firstLink.click();
    await page.waitForURL(/\/elements\//, { timeout: 10000 });
    // Detail page should show tabs and back link
    await expect(page.getByText("Back to elements")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("Summary")).toBeVisible();
  });

  test("element detail shows provenance and annotations", async ({ page }) => {
    await page.goto("/elements/a1b2c3d4e5f6");
    await expect(page.getByText("Provenance")).toBeVisible({ timeout: 15000 });
    await expect(page.locator("text=bids").first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Ontology Annotations")).toBeVisible({ timeout: 5000 });
  });

  test("element detail has tabs", async ({ page }) => {
    await page.goto("/elements/a1b2c3d4e5f6");
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
    await expect(page.getByText("5 total")).toBeVisible({ timeout: 15000 });
    const sourceSelect = page.locator("select").first();
    await expect(sourceSelect).toBeVisible();
  });

  test("column sorting works", async ({ page }) => {
    await page.goto("/elements");
    await expect(page.getByText("5 total")).toBeVisible({ timeout: 15000 });
    // Click a sortable column header (th element)
    const typeHeader = page.locator("thead th").filter({ hasText: "Type" }).first();
    await typeHeader.click();
    // Should see sort indicator arrow
    await expect(page.locator("thead").getByText("↑").or(page.locator("thead").getByText("↓"))).toBeVisible({ timeout: 5000 });
  });
});
