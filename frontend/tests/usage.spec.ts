import { test, expect } from "@playwright/test";

test.use({ timezoneId: "Asia/Kolkata" });

test("workspace usage persists after reload and is isolated when accounts change", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  const created = await page.request.post("/api/workflows", {
    data: {
      prompt: "Create a researched campaign about electric vehicles in India.",
      mode: "demo",
    },
  });
  expect(created.ok()).toBeTruthy();
  await page.goto("/settings");
  const panel = page.getByRole("region", {
    name: "Workflow usage",
    exact: true,
  });
  await expect(panel).toContainText("1 / 50 generation attempts today");
  await expect(panel).toContainText("49 generation attempts remaining today.");
  await page.reload();
  await expect(panel).toContainText("1 / 50 generation attempts today");
  await page.getByTitle("Sign out", { exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.request.post("/api/auth/demo");
  await page.goto("/settings");
  await expect(panel).toContainText("0 / 50 generation attempts today");
  await expect(panel).toContainText("50 generation attempts remaining today.");
});

test("usage handles failures, exhaustion, pause and refresh on mobile", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  let failed = true;
  let daily = 3;
  await page.route("**/api/usage", (route) =>
    failed
      ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      : route.fulfill({
          json: {
            day: "2026-10-25",
            resets_at: "2026-10-26T00:00:00+00:00",
            generation_attempts: 3,
            daily_limit: daily,
            remaining: Math.max(0, daily - 3),
            active_workflows: 2,
            concurrency_limit: 2,
          },
        }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/settings");
  const panel = page.getByRole("region", {
    name: "Workflow usage",
    exact: true,
  });
  await expect(panel.getByRole("alert")).toContainText(
    "Your allowance is unknown",
  );
  failed = false;
  await panel.getByRole("button", { name: "Retry usage" }).click();
  await expect(panel).toContainText("3 / 3 generation attempts today");
  await expect(panel).toContainText("Daily allowance reached");
  await expect(panel).toContainText("All active slots are in use");
  await expect(panel.locator("time")).toHaveAttribute(
    "datetime",
    "2026-10-26T00:00:00+00:00",
  );
  await expect(panel.locator("time")).toContainText("5:30");
  daily = 0;
  await panel.getByRole("button", { name: "Refresh usage" }).click();
  await expect(panel).toContainText(
    "New generation is paused by the site operator",
  );
  daily = 5;
  await panel.getByRole("button", { name: "Refresh usage" }).click();
  await expect(panel).toContainText("2 generation attempts remaining today");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("daily allowance rejection preserves a campaign brief for later retry", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  await page.route("**/api/workflows", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          status: 429,
          headers: { "Retry-After": "60" },
          json: {
            detail:
              "Daily generation allowance reached. Check Settings → Workflow usage.",
          },
        })
      : route.continue(),
  );
  await page.goto("/workflows/new");
  const brief = page.getByLabel("Campaign brief", { exact: true });
  await brief.fill(
    "Create a researched campaign about electric vehicles in India.",
  );
  await page.getByRole("button", { name: "Launch agent team" }).click();
  await expect(
    page.getByText(
      "Daily generation allowance reached. Check Settings → Workflow usage.",
    ),
  ).toBeVisible();
  await expect(brief).toHaveValue(
    "Create a researched campaign about electric vehicles in India.",
  );
  await expect(
    page.getByRole("button", { name: "Launch agent team" }),
  ).toBeEnabled();
  await expect(page).toHaveURL(/\/workflows\/new$/);
});
