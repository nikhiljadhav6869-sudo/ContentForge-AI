import { test, expect } from "@playwright/test";

test("duplicate reviews the saved brief before creating an independent campaign", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  const original = await page.request.post("/api/workflows", {
    data: {
      prompt: "Create an electric vehicle campaign for city commuters.",
      audience: "City commuters",
      tone: "Precise and technical",
      goals: "Explain transport choices",
      brand: "Careful language with clear sources",
      platforms: ["blog"],
      mode: "demo",
      max_revisions: 0,
      quality_threshold: 93,
    },
  });
  expect(original.ok()).toBeTruthy();
  const originalID = (await original.json()).id;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/workflows/${originalID}`)).json())
          .status,
    )
    .toBe("awaiting_approval");
  const before = await (
    await page.request.get(`/api/workflows/${originalID}`)
  ).json();
  await page.goto(`/control/${originalID}`);
  await page.getByRole("button", { name: "Duplicate campaign" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/workflows/new\\?from=${originalID}$`),
  );
  await expect(page.getByLabel("Campaign brief", { exact: true })).toHaveValue(
    before.brief.prompt,
  );
  await expect(page.getByLabel("Who is this for?")).toHaveValue(
    "City commuters",
  );
  await expect(page.getByLabel("Voice & tone")).toHaveValue(
    "Precise and technical",
  );
  await expect(page.getByLabel("Brand voice")).toHaveValue(before.brief.brand);
  await expect(
    page.getByRole("button", { name: /Blog article/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: /LinkedIn/ })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  expect((await (await page.request.get("/api/workflows")).json()).length).toBe(
    1,
  );
  await page
    .getByLabel("Campaign brief", { exact: true })
    .fill("Create a second electric vehicle campaign for students.");
  await page.getByLabel("Who is this for?").fill("University students");
  await page
    .getByRole("button", { name: "Advanced workflow settings" })
    .click();
  await expect(page.getByLabel("Quality threshold")).toHaveValue("93");
  await expect(page.getByLabel("Maximum automatic revisions")).toHaveValue("0");
  await page.getByLabel("Quality threshold").fill("87");
  await page
    .getByRole("button", { name: "Advanced workflow settings" })
    .click();
  await expect(page.getByLabel("Quality threshold")).toBeHidden();
  await page.getByRole("button", { name: "Launch agent team" }).click();
  await expect(page).toHaveURL(/\/control\/[^/?]+$/);
  const newID = page.url().split("/").at(-1)!;
  expect(newID).not.toBe(originalID);
  const copied = await (
    await page.request.get(`/api/workflows/${newID}`)
  ).json();
  expect(copied.project_id).not.toBe(before.project_id);
  expect(copied.brief.audience).toBe("University students");
  expect(copied.brief.quality_threshold).toBe(87);
  expect(copied.brief.max_revisions).toBe(0);
  expect(copied.reviews).toEqual([]);
  expect(
    await (await page.request.get(`/api/workflows/${originalID}`)).json(),
  ).toEqual(before);
});

test("unavailable duplicate offers retry without presenting an empty launch form", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  await page.goto("/workflows/new?from=missing-campaign");
  await expect(page.getByText("Workflow not found.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Try again", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Launch agent team" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByText("Workflow not found.")).toBeVisible();
});

test("copied live settings and older sources remain visible when the provider is unavailable", async ({
  page,
}) => {
  await page.request.post("/api/auth/demo");
  // Simulate a previously configured provider, without sending paid model requests.
  await page.route("**/api/workflows/live-fixture/brief", (route) =>
    route.fulfill({
      json: {
        prompt: "Create a campaign using the original reference material.",
        audience: "Researchers",
        tone: "Precise and technical",
        goals: "Explain findings",
        brand: "Careful language",
        platforms: ["linkedin"],
        mode: "openai",
        source_ids: ["older-reference"],
        max_revisions: 0,
        quality_threshold: 93,
      },
    }),
  );
  let settingsRequests = 0;
  let settingsUnavailable = false;
  await page.route("**/api/settings", async (route) => {
    settingsRequests++;
    if (settingsUnavailable) {
      await route.fulfill({
        status: 503,
        json: { detail: "Settings temporarily unavailable" },
      });
      return;
    }
    const response = await route.fetch();
    const settings = await response.json();
    settings.providers.openai = false;
    settings.preferences.default_provider = "demo";
    await route.fulfill({ json: settings });
  });
  await page.route("**/api/sources", (route) =>
    route.fulfill({
      json: [
        ...Array.from({ length: 12 }, (_, index) => ({
          id: `recent-${index}`,
          title: `Recent reference ${index}`,
          kind: "upload",
        })),
        {
          id: "older-reference",
          title: "Original older reference",
          kind: "upload",
        },
      ],
    }),
  );
  await page.goto("/workflows/new?from=live-fixture");
  await expect(
    page.getByRole("combobox", { name: "Execution mode" }),
  ).toHaveValue("openai");
  await expect(
    page.getByRole("checkbox", { name: "Original older reference upload" }),
  ).toBeChecked();
  await expect(
    page.getByRole("button", { name: "Launch agent team" }),
  ).toBeDisabled();
  await expect(page.getByText(/This provider is unavailable/)).toBeVisible();
  await page.getByLabel("Brand voice").fill("My edited brand voice");
  settingsUnavailable = true;
  const previousRequests = settingsRequests;
  const failedRefresh = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/settings") && response.status() === 503,
  );
  await expect
    .poll(async () => {
      await page.evaluate(() =>
        window.dispatchEvent(new Event("visibilitychange")),
      );
      return settingsRequests;
    })
    .toBeGreaterThan(previousRequests);
  await failedRefresh;
  await expect(page.getByLabel("Brand voice")).toHaveValue(
    "My edited brand voice",
  );
  await page
    .getByRole("combobox", { name: "Execution mode" })
    .selectOption("demo");
  await expect(
    page.getByRole("button", { name: "Launch agent team" }),
  ).toBeEnabled();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/duplicate-mobile.png",
    fullPage: true,
  });
});
