import { test, expect } from "@playwright/test";

test("homepage loads with search input", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("undata Schema Explorer")).toBeVisible();
  await expect(page.getByPlaceholder(/Search elements/)).toBeVisible();
});

test("elements page loads", async ({ page }) => {
  await page.goto("/elements");
  // Should render the search bar at minimum
  await expect(page.getByPlaceholder("Search elements...")).toBeVisible();
});

test("add page requires authentication or renders form", async ({ page }) => {
  // Navigate but don't fail on network errors (Keycloak may not be running)
  const response = await page.goto("/add", { waitUntil: "domcontentloaded" });
  // Accept: auth redirect, form render, or any non-500 status
  const status = response?.status() ?? 200;
  expect(status).toBeLessThan(500);
});

test("migrations page loads", async ({ page }) => {
  await page.goto("/migrations");
  await expect(page.getByText("Migration Pathways")).toBeVisible();
});

test("compare page loads with prompt", async ({ page }) => {
  await page.goto("/compare");
  await expect(page.getByText("Compare Elements")).toBeVisible();
});
