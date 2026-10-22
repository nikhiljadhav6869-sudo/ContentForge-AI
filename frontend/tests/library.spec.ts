import { test, expect } from "@playwright/test";

test.use({ actionTimeout: 20000 });

test("campaign library supports search, pagination, saved filters and mobile navigation", async ({
  page,
}) => {
  test.setTimeout(180000);
  await page.request.post("/api/auth/demo");
  for (let index = 1; index <= 8; index++) {
    const created = await page.request.post("/api/workflows", {
      data: {
        prompt: `Library campaign ${String(index).padStart(2, "0")}: an educational campaign about electric vehicles.`,
        mode: "demo",
      },
    });
    expect(created.ok()).toBeTruthy();
    const id = (await created.json()).id;
    const cancelled = await page.request.post(`/api/workflows/${id}/cancel`);
    expect(cancelled.ok()).toBeTruthy();
  }
  await page.goto("/dashboard");
  const library = page.getByRole("region", {
    name: "Campaign library",
    exact: true,
  });
  const rows = library.locator(".run-row");
  await expect(rows).toHaveCount(6);
  const firstPage = await rows.allTextContents();
  await library.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(rows).toHaveCount(2);
  expect(
    (await rows.allTextContents()).every((row) => !firstPage.includes(row)),
  ).toBe(true);
  await expect(
    library.getByRole("button", { name: "Next", exact: true }),
  ).toBeDisabled();

  await page
    .getByLabel("Search campaigns", { exact: true })
    .fill("campaign 03");
  await library.getByRole("button", { name: "Search", exact: true }).click();
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("Library campaign 03");
  expect(new URL(page.url()).searchParams.has("page")).toBe(false);
  await page.reload();
  await expect(
    page.getByLabel("Search campaigns", { exact: true }),
  ).toHaveValue("campaign 03");
  await expect(rows).toHaveCount(1);
  await page.goBack();
  await expect(rows).toHaveCount(2);
  await expect(
    page.getByLabel("Search campaigns", { exact: true }),
  ).toHaveValue("");

  await library.getByRole("button", { name: "Clear filters" }).click();
  await page
    .getByRole("combobox", { name: "Campaign status", exact: true })
    .selectOption("completed");
  await expect(
    library.getByRole("heading", { name: "No campaigns match your filters" }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Campaign status", exact: true })
    .selectOption("cancelled");
  await expect(rows).toHaveCount(6);
  await expect(library.getByRole("status").first()).toContainText(
    "of 8 campaigns",
  );
  await page
    .getByRole("combobox", { name: "Campaign order", exact: true })
    .selectOption("oldest");
  await expect(rows.first()).toContainText("Library campaign 01");
  await page.reload();
  await expect(
    page.getByRole("combobox", { name: "Campaign status", exact: true }),
  ).toHaveValue("cancelled");
  await expect(
    page.getByRole("combobox", { name: "Campaign order", exact: true }),
  ).toHaveValue("oldest");

  await library.screenshot({
    path: "test-results/campaign-library-desktop.png",
  });
  await page.goto("/dashboard?status=cancelled&page=99");
  await expect(
    library.getByRole("heading", { name: "This page has no campaigns" }),
  ).toBeVisible();
  await library.getByRole("button", { name: "Go to first page" }).click();
  await expect(rows).toHaveCount(6);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByLabel("Search campaigns", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
  await library.screenshot({
    path: "test-results/campaign-library-mobile.png",
  });
  await rows.first().click();
  await expect(page).toHaveURL(/\/control\//);
  const selectedId = page.url().split("/").at(-1)!;
  // Simulate a valid older campaign outside the recent picker's capped list.
  await page.route("**/api/workflows", (route) => route.fulfill({ json: [] }));
  await page.goto("/dashboard");
  await page.setViewportSize({ width: 1440, height: 1000 });
  const controlLink = page.getByRole("link", {
    name: "Agent control center",
    exact: true,
  });
  await expect(controlLink).toHaveAttribute("href", `/control/${selectedId}`);
  await controlLink.click();
  await expect(page.getByLabel("Choose campaign", { exact: true })).toHaveValue(
    selectedId,
  );
});

test("campaign library exposes failed requests and can retry", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  await page.route("**/api/campaigns?*", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Campaign search is temporarily unavailable." },
    }),
  );
  await page.goto("/dashboard");
  const library = page.getByRole("region", {
    name: "Campaign library",
    exact: true,
  });
  await expect(
    library.getByText("Campaign search is temporarily unavailable."),
  ).toBeVisible();
  await expect(library.getByText("Start something worth sharing")).toHaveCount(
    0,
  );
  await page.unroute("**/api/campaigns?*");
  await library.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    library.getByRole("heading", { name: "Start something worth sharing" }),
  ).toBeVisible();
});
