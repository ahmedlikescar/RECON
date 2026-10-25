import { test, expect } from "@playwright/test";

test("load real demo, inspect assembly and CFG, compare and export", async ({
  page,
}) => {
  const errors: string[] = [];
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    if (
      /^https?:/.test(request.url()) &&
      !request.url().startsWith("http://127.0.0.1:8001/")
    )
      externalRequests.push(request.url());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Binary workspace" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Load demo" }).click();
  await expect(
    page.getByRole("button", { name: /^demo-O0\.elf/ }).last(),
  ).toBeVisible();
  await expect(page.locator("tbody .status-completed")).toHaveCount(2, {
    timeout: 20000,
  });
  await page.screenshot({ path: "test-results/workspace.png", fullPage: true });
  await page
    .getByRole("button", { name: /^demo-O0\.elf/ })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: "demo-O0.elf" }),
  ).toBeVisible();
  const analysisDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export analysis" }).click();
  expect((await analysisDownload).suggestedFilename()).toMatch(/\.json$/);
  await page
    .getByRole("button", { name: /checksum_bytes/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "checksum_bytes" }),
  ).toBeVisible();
  await expect(page.locator(".instructions tbody tr")).not.toHaveCount(0);
  await page.getByRole("button", { name: /Control flow/ }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  await page.screenshot({ path: "test-results/explorer.png", fullPage: true });
  await page.getByRole("button", { name: "Find similar functions" }).click();
  await page.getByLabel("Target binary").selectOption({ label: "demo-O2.elf" });
  await page
    .getByRole("button", { name: "Compare functions", exact: true })
    .click();
  await expect(
    page.getByText("COMPARISON RESULTS", { exact: true }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".candidate-row").first()).toContainText(
    "checksum_bytes",
  );
  await expect(page.locator(".side-by-side .evidence")).toHaveCount(2);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "JSON", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/^recon-.*\.json$/);
  await page.screenshot({
    path: "test-results/comparison.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
  expect(externalRequests).toEqual([]);
});

test("reject invalid upload with actionable error and keep the workspace usable", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Import binary file").setInputFiles({
    name: "invalid.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("MZbad"),
  });
  await expect(page.getByRole("alert")).toContainText("supports x86-64 ELF");
  await page.getByRole("button", { name: "Dismiss error" }).click();
  await expect(
    page.getByRole("heading", { name: "Binary workspace" }),
  ).toBeVisible();
});

test("show optional provider state and usable narrow layout", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Integrations", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "REA + Ghidra" }),
  ).toBeVisible();
  await expect(
    page.getByText("Optional · disabled", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
