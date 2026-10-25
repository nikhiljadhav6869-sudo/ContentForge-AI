import { test, expect } from "@playwright/test";

test("closed registration and disabled guests direct visitors to existing-account sign-in", async ({
  page,
}) => {
  await page.route("**/api/auth/options", (route) =>
    route.fulfill({
      json: { registration: false, demo: false, password_reset: false },
    }),
  );
  await page.goto("/");
  await expect(
    page.getByText(
      "Account registration is closed. Contact the site operator for access.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Explore the live demo" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Start creating", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await expect(page.getByLabel("Your name")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "New here? Create an account" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Forgot your password?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close sign-in" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Build your first campaign" }).click();
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("options outage allows sign-in and can recover registration choices", async ({
  page,
}) => {
  let failed = true;
  await page.route("**/api/auth/options", (route) =>
    failed
      ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      : route.fulfill({
          json: { registration: true, demo: true, password_reset: false },
        }),
  );
  await page.goto("/");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Sign-up options could not load" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close sign-in" }).click();
  failed = false;
  await page.getByRole("button", { name: "Retry sign-up options" }).click();
  await expect(
    page.getByRole("button", { name: "Explore the live demo" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Start creating", exact: true })
    .click();
  await expect(page.getByLabel("Your name")).toBeVisible();
});

test("server rejection of a stale open registration form preserves entries", async ({
  page,
}) => {
  await page.route("**/api/auth/options", (route) =>
    route.fulfill({
      json: { registration: true, demo: false, password_reset: false },
    }),
  );
  await page.route("**/api/auth/register", (route) =>
    route.fulfill({
      status: 403,
      json: {
        detail:
          "Account registration is closed. Contact the site operator for access.",
      },
    }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "Start creating", exact: true })
    .click();
  await page.getByLabel("Your name").fill("New creator");
  await page.getByLabel("Email", { exact: true }).fill("new@example.com");
  await page.getByLabel(/^Password/).fill("test-password-2026");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByText(
      "Account registration is closed. Contact the site operator for access.",
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Email", { exact: true })).toHaveValue(
    "new@example.com",
  );
  await page
    .getByRole("button", { name: "Already have an account? Sign in" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
});
