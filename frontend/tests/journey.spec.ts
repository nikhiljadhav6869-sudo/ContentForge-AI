import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("complete campaign: graph, evidence, edit, approval, export, calendar", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /One idea/ })).toBeVisible();
  await page.getByRole("button", { name: "Explore the live demo" }).click();
  await expect(page).toHaveURL(/\/control\//, { timeout: 60000 });
  await expect(
    page.getByRole("heading", { name: /Agent control center/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review content", exact: true }),
  ).toBeVisible({ timeout: 60000 });
  const runId = page.url().split("/").at(-1)!;
  await expect(page.getByTestId("agent-supervisor")).toHaveClass(/completed/);
  await page.getByTestId("agent-writer").click();
  await page.getByRole("button", { name: "Outputs", exact: true }).click();
  await expect(page.locator(".json-preview")).toContainText("artifacts");
  await page.screenshot({
    path: "test-results/control-desktop.png",
    fullPage: true,
  });
  await page.goto(`/evidence/${runId}`);
  await expect(
    page.getByRole("heading", { name: "Evidence inspector" }),
  ).toBeVisible();
  await page
    .getByTestId("claim-highlight")
    .filter({
      hasText: "Battery electric vehicles produce no tailpipe emissions.",
    })
    .click();
  await expect(page.locator(".relation-branch")).toHaveCount(2);
  await page
    .getByLabel("Evidence version")
    .selectOption({ label: "Version 1" });
  await page
    .getByTestId("claim-highlight")
    .filter({
      hasText:
        "Electric vehicles are emission-free across their entire lifecycle.",
    })
    .click();
  await expect(page.locator(".evidence-inspector .badge")).toContainText(
    "Disputed",
  );
  await page.screenshot({
    path: "test-results/evidence-desktop.png",
    fullPage: true,
  });
  await page.goto(`/content/${runId}`);
  await page.getByRole("button", { name: "Edit document" }).click();
  const editor = page.getByRole("textbox", { name: "Content editor" });
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type(
    " Additional statement requires human evidence review.",
  );
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(
    page.getByText("New version saved. Evidence status reset for review."),
  ).toBeVisible();
  await page.locator("#comment").fill("Reviewed the new wording.");
  await page.getByRole("button", { name: "Add comment", exact: true }).click();
  await expect(page.locator(".comment")).toContainText(
    "Reviewed the new wording.",
  );
  await page
    .getByRole("checkbox", {
      name: "I reviewed the remaining evidence warnings.",
    })
    .check();
  await page.getByRole("button", { name: "Approve current versions" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Approved and ready for your next step.",
    }),
  ).toBeVisible({ timeout: 30000 });
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export campaign", exact: true })
    .click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("contentforge-campaign.md");
  const packagePromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download ZIP package", exact: true })
    .click();
  const packageDownload = await packagePromise;
  expect(packageDownload.suggestedFilename()).toBe("contentforge-campaign.zip");
  const packageBytes = await readFile((await packageDownload.path())!);
  expect(packageBytes.subarray(0, 4).toString("hex")).toBe("504b0304");
  await page.goto("/calendar");
  await page.getByLabel("Approved campaign").selectOption(runId);
  await page.getByLabel("Content format").selectOption({ label: "Blog" });
  const future = new Date(Date.now() + 86400000);
  const localDate = new Date(
    future.getTime() - future.getTimezoneOffset() * 60000,
  )
    .toISOString()
    .slice(0, 16);
  await page.getByLabel("Schedule date").fill(localDate);
  await page.getByRole("button", { name: "Add to calendar" }).click();
  await expect(page.locator(".schedule-list")).toContainText("Blog");
  await page.goto("/analytics");
  await expect(
    page.getByRole("heading", { name: "Execution performance" }),
  ).toBeVisible();
  await page.goto("/settings");
  await page.getByLabel("Brand name").fill("Evidence Studio");
  await page.getByLabel("Preferred export format").selectOption("zip");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await page.reload();
  await expect(page.getByLabel("Brand name")).toHaveValue("Evidence Studio");
  await expect(page.getByLabel("Preferred export format")).toHaveValue("zip");
  await page.goto(`/content/${runId}`);
  const preferredDownload = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export campaign", exact: true })
    .click();
  expect((await preferredDownload).suggestedFilename()).toBe(
    "contentforge-campaign.zip",
  );
  expect(errors).toEqual([]);
});

test("guided form, project creation, mobile and tablet layouts", async ({
  page,
}) => {
  test.setTimeout(240000);
  await page.goto("/");
  await page.request.post("/api/auth/demo");
  await page.goto("/workflows/new");
  await page
    .getByLabel("Campaign brief")
    .fill("Create an educational campaign about electric vehicles in India.");
  await page.getByRole("button", { name: "Launch agent team" }).click();
  await expect(page).toHaveURL(/\/control\//, { timeout: 30000 });
  const id = page.url().split("/").at(-1)!;
  await expect(
    page.getByRole("button", { name: "Review content", exact: true }),
  ).toBeVisible({ timeout: 60000 });
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [
      "/dashboard",
      `/control/${id}`,
      `/evidence/${id}`,
      `/content/${id}`,
      "/workflows/new",
      "/analytics",
      "/approvals",
      "/calendar",
      "/settings",
    ]) {
      await page.goto(path);
      await expect(page.locator("h1").first()).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth + 1,
          ),
        )
        .toBe(true);
    }
    await page.screenshot({
      path: `test-results/settings-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/control/${id}`);
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await expect(page.locator(".sidebar")).toHaveClass(/open/);
  await page
    .getByRole("button", { name: "Close navigation", exact: true })
    .click();
  await page.getByTestId("agent-research").click();
  await expect(page.locator(".agent-inspector")).toHaveClass(/mobile-open/);
  await page.getByRole("button", { name: "Close inspector" }).click();
  await page.screenshot({
    path: "test-results/control-mobile.png",
    fullPage: true,
  });
});

test("SSE cursor replay returns missed persisted events", async ({ page }) => {
  await page.goto("/");
  await page.request.post("/api/auth/demo");
  const created = await page.request.post("/api/workflows", {
    data: {
      prompt: "Create a researched campaign about electric vehicles in India.",
      mode: "demo",
    },
  });
  const id = (await created.json()).id;
  await expect
    .poll(
      async () => {
        const r = await page.request.get(`/api/workflows/${id}`);
        return (await r.json()).status;
      },
      { timeout: 60000 },
    )
    .toBe("awaiting_approval");
  const seq = await page.evaluate(async (id) => {
    const controller = new AbortController();
    const response = await fetch(`/api/workflows/${id}/events`, {
      headers: { "Last-Event-ID": "5" },
      signal: controller.signal,
    });
    const reader = response.body!.getReader();
    let data = "";
    while (!data.includes("\n\n")) {
      const chunk = await reader.read();
      data += new TextDecoder().decode(chunk.value);
    }
    controller.abort();
    return Number(data.match(/id: (\d+)/)?.[1]);
  }, id);
  expect(seq).toBe(6);
});
