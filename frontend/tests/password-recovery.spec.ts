import { test, expect } from "@playwright/test";

test("sign-in links to recovery and unconfigured delivery is explained", async ({
  page,
}) => {
  await page.route("**/api/auth/options", (route) =>
    route.fulfill({ json: { password_reset: false } }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Forgot your password?" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(
    page.getByText(
      "Password recovery is unavailable. Contact the site operator.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Request reset link" }),
  ).toHaveCount(0);
});

test("request form recovers from availability and delivery errors", async ({
  page,
}) => {
  let available = false;
  await page.route("**/api/auth/options", (route) =>
    available
      ? route.fulfill({ json: { password_reset: true } })
      : route.fulfill({ status: 503, json: { detail: "Unavailable" } }),
  );
  let fail = true;
  await page.route("**/api/auth/forgot-password", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      email: "person@example.com",
    });
    await route.fulfill(
      fail
        ? {
            status: 503,
            json: { detail: "Recovery temporarily unavailable. Please retry." },
          }
        : {
            status: 202,
            json: {
              message:
                "If an account matches that address, a reset link will arrive shortly. Check your spam folder too.",
            },
          },
    );
  });
  await page.goto("/forgot-password");
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Could not check password recovery",
  );
  available = true;
  await page.getByRole("button", { name: "Try again" }).click();
  await page.getByLabel("Email", { exact: true }).fill("person@example.com");
  await page.getByRole("button", { name: "Request reset link" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Recovery temporarily unavailable",
  );
  await expect(page.getByLabel("Email", { exact: true })).toHaveValue(
    "person@example.com",
  );
  fail = false;
  await page.getByRole("button", { name: "Request reset link" }).click();
  await expect(page.getByRole("status")).toContainText("If an account matches");
  await expect(
    page.getByRole("button", { name: "Request reset link" }),
  ).toHaveCount(0);
});

test("reset keeps the token out of URLs, checks confirmation, and supports retry on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const token = "a".repeat(43);
  let attempts = 0;
  const urls: string[] = [];
  page.on("request", (request) => urls.push(request.url()));
  await page.route("**/api/auth/reset-password", async (route) => {
    attempts++;
    expect(route.request().postDataJSON()).toEqual({
      token,
      password: "new-password-123",
    });
    await route.fulfill(
      attempts === 1
        ? {
            status: 503,
            json: { detail: "Service unavailable. Please retry." },
          }
        : {
            json: {
              message: "Password updated. Sign in with your new password.",
            },
          },
    );
  });
  await page.goto(`/reset-password#token=${token}`);
  await expect(page).toHaveURL(/\/reset-password$/);
  await page
    .getByLabel("New password", { exact: true })
    .fill("new-password-123");
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("different-password");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "The passwords do not match.",
  );
  expect(attempts).toBe(0);
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("new-password-123");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Service unavailable",
  );
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByRole("status")).toContainText("Password updated");
  expect(urls.every((url) => !url.includes(token))).toBeTruthy();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "missing a valid reset token",
  );
});

test("invalid and expired reset links offer a new request", async ({
  page,
}) => {
  await page.goto("/reset-password#token=invalid");
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "missing a valid reset token",
  );
  await expect(page.getByLabel("New password", { exact: true })).toHaveCount(0);
  await page.route("**/api/auth/reset-password", (route) =>
    route.fulfill({
      status: 400,
      json: {
        detail: "This reset link is invalid or expired. Request a new link.",
      },
    }),
  );
  await page.goto(`/reset-password#token=${"b".repeat(43)}`);
  await page
    .getByLabel("New password", { exact: true })
    .fill("new-password-123");
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("new-password-123");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "invalid or expired",
  );
  await page.getByRole("link", { name: "Request a new link" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
});
