import { test, expect } from "@playwright/test";

test("service status reports failures, recovery, and an offline browser", async ({
  page,
  context,
}) => {
  await page.request.post("/api/auth/demo");
  let unavailable = true;
  await page.route("**/api/health", async (route) => {
    if (unavailable)
      await route.fulfill({
        status: 503,
        json: { detail: "Queue unavailable" },
      });
    else await route.continue();
  });
  await page.goto("/dashboard");
  const status = page.getByRole("button", { name: "Check service connection" });
  await expect(status).toHaveAttribute("data-state", "unavailable");
  await expect(status).toContainText("Connection unavailable");
  unavailable = false;
  await status.click();
  await expect(status).toHaveAttribute("data-state", "available");
  await expect(status).toContainText("API available");
  await context.setOffline(true);
  await expect(status).toHaveAttribute("data-state", "offline");
  await context.setOffline(false);
  await expect(status).toHaveAttribute("data-state", "available");
});

test("a service outage offers retry without treating the account as signed out", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  await page.route("**/api/me", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Service temporarily unavailable." },
    }),
  );
  await page.goto("/dashboard");
  await expect(
    page.getByText("Service temporarily unavailable."),
  ).toBeVisible();
  await expect(page.getByText("Your creative workspace awaits.")).toHaveCount(
    0,
  );
  await page.unroute("**/api/me");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.locator(".app-shell")).toBeVisible();
});

test("demo startup does not replace an account when identity lookup fails", async ({
  page,
}) => {
  let guestAttempts = 0;
  await page.route("**/api/me", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Service temporarily unavailable." },
    }),
  );
  await page.route("**/api/auth/demo", (route) => {
    guestAttempts++;
    return route.fulfill({
      status: 500,
      json: { detail: "Unexpected guest request" },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Explore the live demo" }).click();
  await expect(
    page.getByText("Service temporarily unavailable."),
  ).toBeVisible();
  expect(guestAttempts).toBe(0);
  await expect(page).toHaveURL(/\/$/);
});

test("failed sign-out preserves the workspace; switching accounts clears campaign selection", async ({
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
  const id = (await created.json()).id;
  await page.goto(`/control/${id}`);
  const controlLink = page.getByRole("link", {
    name: "Agent control center",
    exact: true,
  });
  await expect(controlLink).toHaveAttribute("href", `/control/${id}`);
  await page.reload();
  await expect(controlLink).toHaveAttribute("href", `/control/${id}`);

  await page.route("**/api/auth/logout", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Sign-out unavailable. Please retry." },
    }),
  );
  await page.getByTitle("Sign out", { exact: true }).click();
  await expect(
    page.getByText("Sign-out unavailable. Please retry."),
  ).toBeVisible();
  await expect(controlLink).toHaveAttribute("href", `/control/${id}`);
  await page.unroute("**/api/auth/logout");
  await page.getByTitle("Sign out", { exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page
    .getByRole("button", { name: "Start creating", exact: true })
    .click();
  await page.getByLabel("Your name").fill("Recovery Test");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`recovery-${Date.now()}@example.com`);
  await page
    .getByLabel(/^Password/)
    .fill("Test-only-password-2026");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(controlLink).toHaveAttribute("href", "/control");
  await controlLink.click();
  await expect(
    page.getByRole("heading", { name: "Your next campaign starts here" }),
  ).toBeVisible();
  await expect(page.getByText("Workflow not found.")).toHaveCount(0);
});
