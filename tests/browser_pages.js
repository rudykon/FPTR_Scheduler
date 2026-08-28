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
  { width: 360, height: 800 },
  { width: 375, height: 812 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 1000 }
];
const routes = [
  { path: "/", name: "home-zh", home: "zh" },
  { path: "/problem/", name: "problem", interior: true },
  { path: "/method/", name: "method", interior: true },
  { path: "/evidence/", name: "evidence", interior: true, evidence: true },
  { path: "/reproduce/", name: "reproduce", interior: true },
  { path: "/demo/", name: "demo", demo: true },
  { path: "/en/", name: "home-en", home: "en" }
];
const englishSubpageRoutes = [
  { path: "/en/problem/", name: "problem-en", interior: true },
  { path: "/en/method/", name: "method-en", interior: true },
  { path: "/en/evidence/", name: "evidence-en", interior: true, evidence: true },
  { path: "/en/reproduce/", name: "reproduce-en", interior: true },
  { path: "/en/demo/", name: "demo-en", demo: true }
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
  if (viewport.width <= 390 && route.home === "zh") assert.ok(metrics.heroHeight <= 680, `Chinese mobile hero is ${metrics.heroHeight}px high`);
  if (viewport.width <= 390 && route.home === "en") assert.ok(metrics.heroHeight <= 720, `English mobile hero is ${metrics.heroHeight}px high`);
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
  await current.focus();
  await page.keyboard.press("Escape");
  assert.equal(await toggle.getAttribute("aria-expanded"), "false");
  assert.equal(await toggle.evaluate((node) => document.activeElement === node), true, `${route.name} did not restore focus to its menu button`);
}

async function assertLoadedResources(page, route, responseErrors) {
  const brokenImages = await page.evaluate(() =>
    [...document.images]
      .filter((image) => image.complete && image.naturalWidth === 0)
      .map((image) => image.currentSrc || image.src)
  );
  assert.deepEqual(brokenImages, [], `${route.name} has broken images: ${brokenImages.join(", ")}`);
  assert.deepEqual(responseErrors, [], `${route.name} has failed resources: ${responseErrors.join("; ")}`);
}

async function runLiveDemo(browser, origin, { path: routePath, status, screenshot }) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("response", (response) => {
    if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
  });
  page.on("requestfailed", (request) => errors.push(`request: ${request.url()} ${request.failure()?.errorText || "failed"}`));
  await page.goto(`${origin}${routePath}`, { waitUntil: "load" });
  await page.locator("#runButton").waitFor({ state: "visible", timeout: 30000 });
  await assert.doesNotReject(() => page.waitForFunction(() => !document.querySelector("#runButton").disabled, null, { timeout: 30000 }));
  await page.locator("#runButton").click();
  await page.waitForFunction((expected) => document.querySelector("#dataStatus")?.textContent.includes(expected), status, { timeout: 60000 });
  assert.equal(await page.locator("#comparisonBody tr").count(), 8);
  const postRunWidth = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
  assert.ok(postRunWidth.scroll <= postRunWidth.client + 1, `${routePath} overflows after run: ${postRunWidth.scroll} > ${postRunWidth.client}`);
  await assertLoadedResources(page, { name: routePath }, errors);
  await page.screenshot({ path: path.join(screenshots, screenshot) });
  await context.close();
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

    const noJsContext = await browser.newContext({
      javaScriptEnabled: false,
      viewport: { width: 390, height: 844 }
    });
    const noJsPage = await noJsContext.newPage();
    await noJsPage.goto(`${origin}/`, { waitUntil: "load" });
    assert.equal(await visible(noJsPage.locator("#mainNav")), true, "navigation must remain visible without JavaScript");
    assert.equal(await noJsPage.locator("#mainNav a").count(), 6);
    assert.equal(await visible(noJsPage.locator(".nav-toggle")), false, "inactive menu toggle must be hidden without JavaScript");
    await noJsContext.close();

    let routeChecks = 0;
    for (const viewport of viewports) {
      const context = await browser.newContext({ viewport });
      const viewportRoutes = (viewport.width === 390 || viewport.width === 1440)
        ? [...routes, ...englishSubpageRoutes]
        : routes;
      for (const route of viewportRoutes) {
        const page = await context.newPage();
        const pageErrors = [];
        const responseErrors = [];
        page.on("pageerror", (error) => pageErrors.push(error.message));
        page.on("response", (response) => {
          if (response.status() >= 400) responseErrors.push(`${response.status()} ${response.url()}`);
        });
        page.on("requestfailed", (request) => responseErrors.push(`request failed: ${request.url()} ${request.failure()?.errorText || "failed"}`));
        const response = await page.goto(`${origin}${route.path}`, { waitUntil: "load" });
        assert.ok(response && response.ok(), `${route.path} returned ${response?.status()}`);
        await page.evaluate(() => document.fonts?.ready);
        await assertLayout(page, route, viewport);
        if (viewport.width <= 390) await assertMobileNavigation(page, route);
        if (viewport.width <= 390 && route.evidence) {
          const toggle = page.locator(".rq-toggle");
          assert.equal(await visible(toggle), true);
          await toggle.click();
          assert.equal(await page.locator("#rqNav a").count(), 6);
          assert.equal(await visible(page.locator("#rqNav")), true);
          await page.locator("#rqNav a").first().focus();
          await page.keyboard.press("Escape");
          assert.equal(await toggle.evaluate((node) => document.activeElement === node), true, `${route.name} did not restore focus to the RQ menu button`);
        }
        await assertLoadedResources(page, route, responseErrors);
        const folder = path.join(screenshots, `${viewport.width}x${viewport.height}`);
        await fs.promises.mkdir(folder, { recursive: true });
        await page.screenshot({ path: path.join(folder, `${route.name}.png`) });
        assert.deepEqual(pageErrors, [], `browser errors on ${route.name} at ${viewport.width}px: ${pageErrors.join("; ")}`);
        await page.close();
        routeChecks += 1;
      }
      await context.close();
    }

    await runLiveDemo(browser, origin, {
      path: "/demo/",
      status: "全部实时运行与验证通过",
      screenshot: "demo-live-mobile.png"
    });
    await runLiveDemo(browser, origin, {
      path: "/en/demo/",
      status: "All live runs validated",
      screenshot: "demo-live-mobile-en.png"
    });

    process.stdout.write(`Browser layout checks passed for ${routeChecks} route/viewport combinations, no-JS navigation, and both eight-method live Demos.\n`);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
