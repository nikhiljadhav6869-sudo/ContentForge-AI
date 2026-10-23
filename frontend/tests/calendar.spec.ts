import { test, expect, type Page } from "@playwright/test";

test.use({ timezoneId: "Asia/Kolkata" });

async function createReminder(page: Page) {
  await page.request.post("/api/auth/demo");
  const response = await page.request.post("/api/workflows", {
    data: {
      prompt: "Create an electric vehicle campaign for commuters.",
      mode: "demo",
      platforms: ["blog"],
      max_revisions: 0,
    },
  });
  expect(response.ok()).toBeTruthy();
  const id = (await response.json()).id;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/workflows/${id}`)).json()).status,
    )
    .toBe("awaiting_approval");
  expect(
    (
      await page.request.post(`/api/workflows/${id}/review`, {
        data: { decision: "approve", acknowledge_warnings: true },
      })
    ).ok(),
  ).toBeTruthy();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/workflows/${id}`)).json()).status,
    )
    .toBe("completed");
  const run = await (await page.request.get(`/api/workflows/${id}`)).json();
  const scheduled = await page.request.post("/api/calendar", {
    data: {
      artifact_id: run.artifacts[0].id,
      scheduled_at: new Date(Date.now() + 86400000).toISOString(),
    },
  });
  expect(scheduled.ok()).toBeTruthy();
  return scheduled.json();
}
async function localInput(page: Page, iso: string) {
  return page.evaluate((value) => {
    const date = new Date(value);
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  }, iso);
}

test("move an approved reminder, discard edits, and retain the pinned version across reloads", async ({
  page,
}) => {
  const job = await createReminder(page);
  await page.goto("/calendar");
  const card = page.getByRole("article", { name: /Blog reminder:/ });
  await card.getByRole("button", { name: "Reschedule", exact: true }).click();
  await expect(card.getByLabel("Reschedule blog date")).toHaveValue(
    await localInput(page, job.scheduled_at),
  );
  await card.getByLabel("Reschedule blog date").fill("2000-01-01T10:00");
  await card.getByRole("button", { name: "Save new time" }).click();
  await expect(card.getByRole("alert")).toHaveText(
    "Choose a future date and time.",
  );
  await card.getByRole("button", { name: "Discard changes" }).click();
  expect(
    (await (await page.request.get("/api/calendar")).json())[0].scheduled_at,
  ).toBe(job.scheduled_at);
  await card.getByRole("button", { name: "Reschedule", exact: true }).click();
  const future = new Date(Date.now() + 40 * 86400000);
  future.setUTCSeconds(0, 0);
  await card
    .getByLabel("Reschedule blog date")
    .fill(await localInput(page, future.toISOString()));
  await card.getByRole("button", { name: "Save new time" }).click();
  await expect(
    page.getByText(
      "Reminder rescheduled. The approved content version is unchanged.",
    ),
  ).toBeVisible();
  const moved = (await (await page.request.get("/api/calendar")).json())[0];
  expect(moved.id).toBe(job.id);
  expect(moved.version_id).toBe(job.version_id);
  expect(new Date(moved.scheduled_at).toISOString()).toBe(future.toISOString());
  await expect(page.locator(".calendar-event")).toHaveCount(1);
  await page.reload();
  await expect(card.locator("time")).toHaveAttribute(
    "datetime",
    moved.scheduled_at,
  );
  await card.getByRole("button", { name: "Reschedule", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/reschedule-mobile.png",
    fullPage: true,
  });
  await card.getByRole("button", { name: "Discard changes" }).click();
  await card.getByRole("button", { name: "Cancel blog schedule" }).click();
  await expect(card).toHaveCount(0);
  expect(
    (await (await page.request.get("/api/calendar")).json())[0].status,
  ).toBe("cancelled");
});

test("reschedule preserves edits after errors and rejects a stale editor", async ({
  page,
}) => {
  const job = await createReminder(page);
  await page.goto("/calendar");
  const card = page.getByRole("article", { name: /Blog reminder:/ });
  await card.getByRole("button", { name: "Reschedule", exact: true }).click();
  const edited = await localInput(
    page,
    new Date(Date.now() + 3 * 86400000).toISOString(),
  );
  await card.getByLabel("Reschedule blog date").fill(edited);
  await page.route(`**/api/calendar/${job.id}`, (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Calendar temporarily unavailable" },
    }),
  );
  await card.getByRole("button", { name: "Save new time" }).click();
  await expect(card.getByRole("alert")).toHaveText(
    "Calendar temporarily unavailable",
  );
  await expect(card.getByLabel("Reschedule blog date")).toHaveValue(edited);
  await page.unroute(`**/api/calendar/${job.id}`);
  const elsewhere = await page.request.patch(`/api/calendar/${job.id}`, {
    data: {
      expected_scheduled_at: job.scheduled_at,
      scheduled_at: new Date(Date.now() + 2 * 86400000).toISOString(),
    },
  });
  expect(elsewhere.ok()).toBeTruthy();
  const latest = await elsewhere.json();
  await card.getByRole("button", { name: "Save new time" }).click();
  await expect(card.getByRole("alert")).toContainText(
    "This reminder changed or was cancelled.",
  );
  await expect(card.locator("time")).toHaveAttribute(
    "datetime",
    latest.scheduled_at,
  );
  await expect(card.getByLabel("Reschedule blog date")).toHaveValue(edited);
  await card.getByRole("button", { name: "Discard changes" }).click();
  await card.getByRole("button", { name: "Reschedule", exact: true }).click();
  await expect(card.getByLabel("Reschedule blog date")).toHaveValue(
    await localInput(page, latest.scheduled_at),
  );
});
