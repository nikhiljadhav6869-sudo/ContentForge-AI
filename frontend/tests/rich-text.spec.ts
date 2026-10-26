import { test, expect } from "@playwright/test";

async function campaign(page: import("@playwright/test").Page) {
  await page.request.post("/api/auth/demo");
  const response = await page.request.post("/api/workflows", {
    data: {
      prompt: "Create a researched campaign about electric vehicles in India.",
      mode: "demo",
      platforms: ["blog"],
    },
  });
  expect(response.ok()).toBeTruthy();
  const id = (await response.json()).id;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/workflows/${id}`)).json()).status,
      { timeout: 60000 },
    )
    .toBe("awaiting_approval");
  return id;
}

test("bold italic and lists survive saving reload approval and Markdown export", async ({
  page,
}) => {
  const id = await campaign(page);
  await page.goto(`/content/${id}`);
  await page
    .getByRole("button", { name: "Edit document", exact: true })
    .click();
  const editor = page.getByRole("textbox", { name: "Content editor" });
  await editor.fill("Battery electric vehicles produce no tailpipe emissions.");
  await editor.press("Control+a");
  await page.getByRole("button", { name: "Bold", exact: true }).click();
  await page.getByRole("button", { name: "Italic", exact: true }).click();
  await page.getByRole("button", { name: "Bullet list", exact: true }).click();
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(
    page.getByText("New version saved. Evidence status reset for review."),
  ).toBeVisible();
  const formatted = page.locator(".document-body .formatted-document");
  await expect(formatted.locator("li strong")).toContainText(
    "Battery electric vehicles",
  );
  await expect(formatted.locator("li em")).toContainText(
    "Battery electric vehicles",
  );
  await page.reload();
  await expect(formatted.locator("li strong")).toContainText(
    "Battery electric vehicles",
  );
  const run = await (await page.request.get(`/api/workflows/${id}`)).json();
  const current = run.versions.reduce(
    (a: { number: number }, b: { number: number }) =>
      a.number > b.number ? a : b,
  );
  expect(current.document).toBeTruthy();
  expect(
    run.claims
      .filter((c: { version_id: string }) => c.version_id === current.id)
      .every((c: { status: string }) => c.status === "unverified"),
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "Edit document", exact: true })
    .click();
  await expect(editor.locator("li strong")).toBeVisible();
  await page.getByRole("button", { name: "Cancel edit" }).click();
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
  ).toBeVisible();
  const markdown = await (
    await page.request.get(`/api/workflows/${id}/export`)
  ).text();
  expect(markdown).toContain("- ***Battery electric vehicles");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(formatted.locator("li")).toContainText(
    "Battery electric vehicles",
  );
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBeTruthy();
});

test("stale editor keeps unsaved text and formatting while rejecting an overwrite", async ({
  page,
}) => {
  const id = await campaign(page);
  await page.goto(`/content/${id}`);
  await page
    .getByRole("button", { name: "Edit document", exact: true })
    .click();
  const editor = page.getByRole("textbox", { name: "Content editor" });
  await editor.fill("Unsaved changes must stay in this editor.");
  await editor.press("Control+a");
  await page.getByRole("button", { name: "Bold", exact: true }).click();
  const run = await (await page.request.get(`/api/workflows/${id}`)).json();
  const version = run.versions.reduce(
    (a: { number: number }, b: { number: number }) =>
      a.number > b.number ? a : b,
  );
  const edit = await page.request.put(`/api/artifacts/${version.artifact_id}`, {
    data: {
      body: "Another tab saved this different content.",
      base_version: version.number,
    },
  });
  expect(edit.ok()).toBeTruthy();
  await page.getByRole("button", { name: "Save version" }).click();
  await expect(
    page.getByText(
      "This document changed in another tab. Reload before saving.",
    ),
  ).toBeVisible();
  await expect(editor.locator("strong")).toHaveText(
    "Unsaved changes must stay in this editor.",
  );
  const after = await (await page.request.get(`/api/workflows/${id}`)).json();
  expect(
    after.versions.filter((v: { number: number }) => v.number > version.number),
  ).toHaveLength(1);
  await page.getByRole("button", { name: "Cancel edit" }).click();
  await page.reload();
  await expect(page.locator(".document-body")).toContainText(
    "Another tab saved this different content.",
  );
});

test("literal HTML stays inert and emoji do not break evidence offsets", async ({
  page,
}) => {
  const id = await campaign(page);
  const run = await (await page.request.get(`/api/workflows/${id}`)).json();
  const version = run.versions.reduce(
    (a: { number: number }, b: { number: number }) =>
      a.number > b.number ? a : b,
  );
  const first = '🚗 <img src=x onerror="alert(1)">';
  const claim = "Battery electric vehicles produce no tailpipe emissions.";
  const document = {
    type: "doc",
    content: [
      { type: "paragraph", content: [{ type: "text", text: first }] },
      {
        type: "paragraph",
        content: [{ type: "text", text: claim, marks: [{ type: "bold" }] }],
      },
    ],
  };
  const response = await page.request.put(
    `/api/artifacts/${version.artifact_id}`,
    {
      data: {
        body: first + "\n\n" + claim,
        document,
        base_version: version.number,
      },
    },
  );
  expect(response.ok()).toBeTruthy();
  await page.goto(`/content/${id}`);
  await expect(page.locator(".document-body")).toContainText(first);
  await expect(page.locator(".document-body img")).toHaveCount(0);
  await page.goto(`/evidence/${id}`);
  const highlight = page
    .getByTestId("claim-highlight")
    .filter({ hasText: claim });
  await expect(highlight).toBeVisible();
  await highlight.click();
  await expect(page.locator(".evidence-inspector blockquote")).toHaveText(
    claim,
  );
});
