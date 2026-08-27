"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const siteRoot = path.resolve(process.argv[2] || "_site");
const screenshots = path.resolve(process.argv[3] || "artifacts/browser");
const basePath = "/FPTR_Scheduler";
const viewports = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 1000 }
];
const routes = [
  { path: "/", name: "home-zh", home: "zh" },
  { path: "/problem/", name: "problem", interior: true },
  { path: "/method/", name: "method", interior: true },
  { path: "/evidence/", name: "evidence", interior: true },
  { path: "/reproduce/", name: "reproduce", interior: true },
  { path: "/demo/", name: "demo" },
  { path: "/en/", name: "home-en", home: "en" }
];
const mime = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".in": "text/plain; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".wasm": "application/wasm",
  ".webp": "image/webp"
};

function staticServer() {
  return http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, "http://127.0.0.1");
      if (!url.pathname.startsWith(`${basePath}/`) && url.pathname !== basePath) {
        response.writeHead(404).end("Not found");
        return;
      }
      let relative = url.pathname.slice(basePath.length).replace(/^\/+/, "");
      if (!relative || relative.endsWith("/")) relative += "index.html";
      const file = path.resolve(siteRoot, relative);
      if (file !== siteRoot && !file.startsWith(`${siteRoot}${path.sep}`)) {
        response.writeHead(403).end("Forbidden");
        return;
      }
      const payload = await fs.promises.readFile(file);
      response.writeHead(200, {
        "content-type": mime[path.extname(file)] || "application/octet-stream",
        "cache-control": "no-store"
      });
      response.end(payload);
    } catch (error) {
      response.writeHead(error.code === "ENOENT" ? 404 : 500).end("Not found");
    }
  });
}

async function listen(server) {
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return server.address().port;
}

async function visible(element) {
  return element.evaluate((node) => {
    const style = getComputedStyle(node);
    const box = node.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
  });
}

async function assertLayout(page, route, viewport) {
  const metrics = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    heroHeight: document.querySelector(".page-hero, .home-hero")?.getBoundingClientRect().height || 0,
    smallText: [...document.querySelectorAll("main p, main li, main a, main button, main summary, main label, main th, main td, main h1, main h2, main h3, .site-footer p, .main-nav a")]
      .filter((node) => {
        if (!node.textContent.trim() || node.closest("svg, pre, code, sub, sup, [aria-hidden='true']")) return false;
        const style = getComputedStyle(node);
        const box = node.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      })
      .map((node) => ({ text: node.textContent.trim().slice(0, 60), size: parseFloat(getComputedStyle(node).fontSize) }))
      .filter((item) => item.size < 13.9),
    unfocusableScrollRegions: [...document.querySelectorAll("[data-scroll-region='true']")]
      .filter((node) => node.tabIndex < 0)
      .map((node) => node.className)
  }));
  assert.ok(metrics.scrollWidth <= metrics.clientWidth + 1, `${route.name} overflows at ${viewport.width}px: ${metrics.scrollWidth} > ${metrics.clientWidth}`);
  assert.deepEqual(metrics.smallText, [], `${route.name} contains semantic text below 14px: ${JSON.stringify(metrics.smallText)}`);
  assert.deepEqual(metrics.unfocusableScrollRegions, [], `${route.name} has an unfocusable scroll region`);
  if (route.interior) assert.ok(metrics.heroHeight <= 360, `${route.name} hero is ${metrics.heroHeight}px high`);
  if (viewport.width === 390 && route.home === "zh") assert.ok(metrics.heroHeight <= 680, `Chinese mobile hero is ${metrics.heroHeight}px high`);
  if (viewport.width === 390 && route.home === "en") assert.ok(metrics.heroHeight <= 720, `English mobile hero is ${metrics.heroHeight}px high`);
}

async function assertMobileNavigation(page, route) {
  const toggle = page.locator(".nav-toggle");
  assert.equal(await visible(toggle), true, `${route.name} has no visible mobile menu button`);
  await toggle.click();
  assert.equal(await toggle.getAttribute("aria-expanded"), "true");
  assert.equal(await page.locator("#mainNav a").count(), 6);
  assert.equal(await visible(page.locator("#mainNav")), true);
  const current = page.locator("#mainNav a[aria-current='page']");
  assert.equal(await current.count(), 1, `${route.name} has no current navigation link`);
  assert.equal(await visible(current), true, `${route.name} current navigation link is hidden`);
  await page.keyboard.press("Escape");
  assert.equal(await toggle.getAttribute("aria-expanded"), "false");
}

(async () => {
  await fs.promises.mkdir(screenshots, { recursive: true });
  const server = staticServer();
  const port = await listen(server);
  const origin = `http://127.0.0.1:${port}${basePath}`;
  const browser = await chromium.launch({ headless: true });
  try {
    const requestContext = await browser.newContext();
    const missingZh = await requestContext.request.get(`${origin}/zh/`);
    assert.equal(missingZh.status(), 404, "duplicate /zh/ route must not be published");
    await requestContext.close();

    for (const viewport of viewports) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      const pageErrors = [];
      page.on("pageerror", (error) => pageErrors.push(error.message));
      for (const route of routes) {
        const response = await page.goto(`${origin}${route.path}`, { waitUntil: "load" });
        assert.ok(response && response.ok(), `${route.path} returned ${response?.status()}`);
        await page.evaluate(() => document.fonts?.ready);
        await assertLayout(page, route, viewport);
        if (viewport.width === 390) await assertMobileNavigation(page, route);
        if (viewport.width === 390 && route.name === "evidence") {
          const toggle = page.locator(".rq-toggle");
          assert.equal(await visible(toggle), true);
          await toggle.click();
          assert.equal(await page.locator("#rqNav a").count(), 6);
          assert.equal(await visible(page.locator("#rqNav")), true);
          await page.keyboard.press("Escape");
        }
        const folder = path.join(screenshots, `${viewport.width}x${viewport.height}`);
        await fs.promises.mkdir(folder, { recursive: true });
        await page.screenshot({ path: path.join(folder, `${route.name}.png`) });
      }
      assert.deepEqual(pageErrors, [], `browser errors at ${viewport.width}px: ${pageErrors.join("; ")}`);
      await context.close();
    }

    const demoContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const demo = await demoContext.newPage();
    await demo.goto(`${origin}/demo/`, { waitUntil: "load" });
    await demo.locator("#runButton").waitFor({ state: "visible", timeout: 30000 });
    await assert.doesNotReject(() => demo.waitForFunction(() => !document.querySelector("#runButton").disabled, null, { timeout: 30000 }));
    await demo.locator("#runButton").click();
    await demo.waitForFunction(() => document.querySelector("#dataStatus")?.textContent.includes("全部实时运行与验证通过"), null, { timeout: 60000 });
    assert.equal(await demo.locator("#comparisonBody tr").count(), 8);
    const postRunWidth = await demo.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
    assert.ok(postRunWidth.scroll <= postRunWidth.client + 1, `Demo overflows after run: ${postRunWidth.scroll} > ${postRunWidth.client}`);
    await demo.screenshot({ path: path.join(screenshots, "demo-live-mobile.png") });
    await demoContext.close();

    process.stdout.write(`Browser layout checks passed for ${routes.length} routes at ${viewports.length} viewports, including the eight-method live Demo.\n`);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
