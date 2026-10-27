import { test, expect } from "@playwright/test";

test("demo-only hosting explains live AI and temporary data on desktop and mobile", async ({ page }) => {
  await page.request.post("/api/auth/demo");
  await page.route("**/api/settings", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), demo_only: true } });
  });
  await page.goto("/dashboard");
  const notice = page.getByRole("status").filter({ hasText: "Demo-only hosting" });
  await expect(notice).toContainText("Live AI is disabled");
  await expect(notice).toContainText("demo data may reset");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(notice).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
