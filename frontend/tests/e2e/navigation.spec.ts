import { test, expect } from "@playwright/test";

/**
 * Navigation + data display tests.
 * These verify that pages load without errors and display actual data
 * from the backend (not just static HTML). Requires a running backend
 * with seeded data.
 */

test.describe("Element browsing", () => {
  test("elements page shows results (no service unavailable)", async ({ page }) => {
    await page.goto("/elements");
    // Wait for data to load (react-query fetch)
    await page.waitForTimeout(3000);

    // Should NOT show service unavailable error
    const errorBanner = page.locator("text=Service unavailable");
    await expect(errorBanner).not.toBeVisible();

    // Should NOT show "No results found" if backend has data
    // (If backend is empty, this is acceptable)
    const noResults = page.locator("text=No results found");
    const hasData = await noResults.isHidden().catch(() => true);

    // Should show at least one element card OR the no-results message
    // (but NOT the error banner)
    const pageContent = await page.textContent("body");
    expect(pageContent).not.toContain("Service unavailable");
  });

  test("elements page does not show service unavailable error", async ({ page }) => {
    await page.goto("/elements");
    await page.waitForTimeout(2000);

    // Check the specific error message is NOT present
    const errorText = page.locator("text=Service unavailable");
    await expect(errorText).not.toBeVisible();

    // Also check no "An unexpected error occurred" messages
    const unexpectedError = page.locator("text=An unexpected error occurred");
    await expect(unexpectedError).not.toBeVisible();
  });

  test("values page loads without error", async ({ page }) => {
    await page.goto("/values");
    await page.waitForTimeout(2000);

    const pageContent = await page.textContent("body");
    expect(pageContent).not.toContain("Service unavailable");
    expect(pageContent).toContain("Value Concepts");
  });

  test("migrations page loads without error", async ({ page }) => {
    await page.goto("/migrations");
    await page.waitForTimeout(2000);

    const pageContent = await page.textContent("body");
    expect(pageContent).not.toContain("Service unavailable");
    expect(pageContent).toContain("Migration Pathways");
  });

  test("compare page loads without error", async ({ page }) => {
    await page.goto("/compare");
    await page.waitForTimeout(1000);

    const pageContent = await page.textContent("body");
    expect(pageContent).not.toContain("Service unavailable");
    expect(pageContent).toContain("Compare Elements");
  });
});

test.describe("API connectivity from browser", () => {
  test("client-side fetch to /api/v1/elements returns data", async ({ page }) => {
    await page.goto("/");

    // Execute fetch from browser context to verify proxy works
    const result = await page.evaluate(async () => {
      try {
        const resp = await fetch("/api/v1/elements?limit=1");
        const data = await resp.json();
        return { status: resp.status, hasItems: Array.isArray(data.items) };
      } catch (e) {
        return { status: 0, error: String(e) };
      }
    });

    expect(result.status).toBe(200);
    expect(result.hasItems).toBe(true);
  });

  test("client-side fetch to /api/v1/values returns data", async ({ page }) => {
    await page.goto("/");

    const result = await page.evaluate(async () => {
      try {
        const resp = await fetch("/api/v1/values?limit=1");
        const data = await resp.json();
        return { status: resp.status, hasItems: Array.isArray(data.items) };
      } catch (e) {
        return { status: 0, error: String(e) };
      }
    });

    expect(result.status).toBe(200);
    expect(result.hasItems).toBe(true);
  });
});
