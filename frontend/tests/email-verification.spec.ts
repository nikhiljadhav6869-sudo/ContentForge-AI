import { test, expect } from "@playwright/test";

const unverified = {
  email: "owner@example.com",
  verified_at: null,
  demo_address: false,
  delivery_available: true,
};

test("settings shows verification availability and request retries", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  let configured = false;
  let fail = true;
  await page.route("**/api/auth/email-verification", (route) =>
    route.fulfill({ json: { ...unverified, delivery_available: configured } }),
  );
  await page.route("**/api/auth/email-verification/request", (route) =>
    route.fulfill(
      fail
        ? { status: 503, json: { detail: "Mail temporarily unavailable." } }
        : {
            status: 202,
            json: {
              message:
                "Verification requested. Check your inbox and spam folder.",
            },
          },
    ),
  );
  await page.goto("/settings");
  const panel = page.getByRole("region", { name: "Email verification" });
  await expect(panel.getByText("Not verified", { exact: true })).toBeVisible();
  await expect(
    panel.getByText(
      "Email verification is unavailable. Contact the site operator.",
    ),
  ).toBeVisible();
  configured = true;
  await page.reload();
  await panel.getByRole("button", { name: "Send verification link" }).click();
  await expect(panel.getByRole("alert")).toHaveText(
    "Mail temporarily unavailable.",
  );
  fail = false;
  await panel.getByRole("button", { name: "Send verification link" }).click();
  await expect(panel.getByRole("status")).toContainText(
    "Verification requested",
  );
});

test("confirmation is explicit, clears token URLs, retries, and updates account status on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.request.post("/api/auth/demo");
  const token = "a".repeat(43);
  let verified = false;
  let calls = 0;
  await page.route("**/api/auth/email-verification", (route) =>
    route.fulfill({
      json: {
        ...unverified,
        verified_at: verified ? "2026-10-25T00:00:00+00:00" : null,
      },
    }),
  );
  await page.route("**/api/auth/email-verification/confirm", (route) => {
    calls++;
    expect(route.request().postDataJSON()).toEqual({ token });
    if (calls === 1)
      return route.fulfill({
        status: 503,
        json: { detail: "Service temporarily unavailable." },
      });
    verified = true;
    return route.fulfill({ json: { message: "Your email is verified." } });
  });
  await page.goto(`/verify-email#token=${token}`);
  await expect(page).toHaveURL(/\/verify-email$/);
  const main = page.getByRole("main");
  await expect(main.getByText("Signed in as owner@example.com")).toBeVisible();
  expect(calls).toBe(0);
  await main.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(main.getByRole("alert")).toHaveText(
    "Service temporarily unavailable.",
  );
  await main.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(main.getByRole("status")).toHaveText("Your email is verified.");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await main.getByRole("link", { name: "Open account settings" }).click();
  const panel = page.getByRole("region", { name: "Email verification" });
  await expect(panel.getByText("Verified", { exact: true })).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Send verification link" }),
  ).toHaveCount(0);
});

test("missing links, signed-out users, and wrong-account links have actionable feedback", async ({
  page,
}) => {
  await page.goto("/verify-email");
  const main = page.getByRole("main");
  await expect(main.getByRole("alert")).toContainText(
    "missing a valid verification token",
  );
  await page.goto(`/verify-email#token=${"b".repeat(43)}`);
  await expect(main.getByRole("status")).toContainText(
    "Sign in to the account",
  );
  await expect(
    main.getByRole("button", { name: "Verify email", exact: true }),
  ).toHaveCount(0);
  await page.route("**/api/auth/email-verification", (route) =>
    route.fulfill({ json: unverified }),
  );
  await page.reload();
  await page.goto(`/verify-email#token=${"c".repeat(43)}`);
  await page.route("**/api/auth/email-verification/confirm", (route) =>
    route.fulfill({
      status: 400,
      json: {
        detail:
          "This verification link is invalid, expired, or belongs to another account. Request a new link in Settings.",
      },
    }),
  );
  await main.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(main.getByRole("alert")).toContainText(
    "belongs to another account",
  );
  await page.reload();
  await expect(main.getByRole("alert")).toContainText(
    "missing a valid verification token",
  );
});
