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
  { path: "/problem/", name: "problem", interior: true, equations: 7 },
  { path: "/method/", name: "method", interior: true, equations: 3 },
  { path: "/evidence/", name: "evidence", interior: true, evidence: true, equations: 1 },
  { path: "/reproduce/", name: "reproduce", interior: true },
  { path: "/demo/", name: "demo", demo: true },
  { path: "/en/", name: "home-en", home: "en" }
];
const englishSubpageRoutes = [
  { path: "/en/problem/", name: "problem-en", interior: true, equations: 7 },
  { path: "/en/method/", name: "method-en", interior: true, equations: 3 },
  { path: "/en/evidence/", name: "evidence-en", interior: true, evidence: true, equations: 1 },
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
  const metrics = await page.evaluate(() => {
    const isVisible = (node) => {
      const style = getComputedStyle(node);
      const box = node.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
    };
    const parseColor = (value) => {
      const channels = value.match(/[\d.]+/g)?.map(Number);
      if (!channels || channels.length < 3) return null;
      if (value.startsWith("color(srgb")) {
        return { r: channels[0] * 255, g: channels[1] * 255, b: channels[2] * 255, a: channels[3] ?? 1 };
      }
      return { r: channels[0], g: channels[1], b: channels[2], a: channels[3] ?? 1 };
    };
    const composite = (foreground, background) => {
      const alpha = foreground.a + background.a * (1 - foreground.a);
      if (alpha === 0) return { r: 0, g: 0, b: 0, a: 0 };
      return {
        r: (foreground.r * foreground.a + background.r * background.a * (1 - foreground.a)) / alpha,
        g: (foreground.g * foreground.a + background.g * background.a * (1 - foreground.a)) / alpha,
        b: (foreground.b * foreground.a + background.b * background.a * (1 - foreground.a)) / alpha,
        a: alpha
      };
    };
    const effectiveBackground = (node) => {
      const layers = [];
      for (let current = node; current instanceof Element; current = current.parentElement) {
        const color = parseColor(getComputedStyle(current).backgroundColor);
        if (color && color.a > 0) layers.push(color);
      }
      return layers.reverse().reduce(
        (background, foreground) => composite(foreground, background),
        { r: 255, g: 255, b: 255, a: 1 }
      );
    };
    const linear = (channel) => {
      const value = channel / 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    };
    const luminance = (color) => 0.2126 * linear(color.r) + 0.7152 * linear(color.g) + 0.0722 * linear(color.b);
    const contrast = (left, right) => {
      const lighter = Math.max(luminance(left), luminance(right));
      const darker = Math.min(luminance(left), luminance(right));
      return (lighter + 0.05) / (darker + 0.05);
    };
    const contrastIssues = [...document.querySelectorAll("body *")]
      .filter((node) => {
        const hasDirectText = [...node.childNodes].some(
          (child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim()
        );
        return hasDirectText
          && isVisible(node)
          && !node.closest("svg, pre, code, [aria-hidden='true']");
      })
      .map((node) => {
        const style = getComputedStyle(node);
        const foreground = parseColor(style.color);
        const background = effectiveBackground(node);
        const ratio = foreground ? contrast(foreground, background) : 0;
        const size = parseFloat(style.fontSize);
        const weight = Number.parseInt(style.fontWeight, 10) || 400;
        const large = size >= 24 || (size >= 18.66 && weight >= 700);
        return {
          text: node.textContent.trim().slice(0, 60),
          ratio: Number(ratio.toFixed(2)),
          threshold: large ? 3 : 4.5,
          color: style.color,
          background: style.backgroundColor,
        };
      })
      .filter((item) => item.ratio + 0.01 < item.threshold);
    return {
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      heroHeight: document.querySelector(".page-hero, .home-hero")?.getBoundingClientRect().height || 0,
      demoHeroHeight: document.querySelector(".demo-hero")?.getBoundingClientRect().height || 0,
      heroButtons: [...document.querySelectorAll(".home-hero .hero-actions .button")]
        .filter(isVisible)
        .map((node) => {
          const box = node.getBoundingClientRect();
          return { top: box.top, width: box.width };
        }),
      contrastIssues,
      smallText: [...document.querySelectorAll("main p, main li, main a, main button, main summary, main label, main th, main td, main h1, main h2, main h3, .site-footer p, .main-nav a")]
        .filter((node) => {
          if (!node.textContent.trim() || node.closest("svg, pre, code, sub, sup, [aria-hidden='true']")) return false;
          return isVisible(node);
        })
        .map((node) => ({ text: node.textContent.trim().slice(0, 60), size: parseFloat(getComputedStyle(node).fontSize) }))
        .filter((item) => item.size < 13.9),
      unfocusableScrollRegions: [...document.querySelectorAll("[data-scroll-region='true']")]
        .filter((node) => node.tabIndex < 0)
        .map((node) => node.className)
    };
  });
  assert.ok(metrics.scrollWidth <= metrics.clientWidth + 1, `${route.name} overflows at ${viewport.width}px: ${metrics.scrollWidth} > ${metrics.clientWidth}`);
  assert.deepEqual(metrics.smallText, [], `${route.name} contains semantic text below 14px: ${JSON.stringify(metrics.smallText)}`);
  assert.deepEqual(metrics.contrastIssues, [], `${route.name} contains visible text below WCAG AA contrast: ${JSON.stringify(metrics.contrastIssues)}`);
  assert.deepEqual(metrics.unfocusableScrollRegions, [], `${route.name} has an unfocusable scroll region`);
  if (route.interior) assert.ok(metrics.heroHeight <= 360, `${route.name} hero is ${metrics.heroHeight}px high`);
  if (route.demo) assert.ok(metrics.demoHeroHeight <= 240, `${route.name} Demo hero is ${metrics.demoHeroHeight}px high`);
  if (viewport.width <= 390 && route.home === "zh") assert.ok(metrics.heroHeight <= 680, `Chinese mobile hero is ${metrics.heroHeight}px high`);
  if (viewport.width <= 390 && route.home === "en") {
    assert.ok(metrics.heroHeight <= 720, `English mobile hero is ${metrics.heroHeight}px high`);
    assert.equal(metrics.heroButtons.length, 2, "English mobile home must have two actions");
    assert.ok(Math.abs(metrics.heroButtons[0].top - metrics.heroButtons[1].top) <= 2, "English mobile home actions must share one row");
    assert.ok(Math.abs(metrics.heroButtons[0].width - metrics.heroButtons[1].width) <= 2, "English mobile home actions must have equal widths");
  }
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

async function assertEquations(page, route) {
  const result = await page.evaluate(async () => {
    const details = [...document.querySelectorAll("details")].filter((node) => node.querySelector(".formula-block"));
    const previous = details.map((node) => node.open);
    details.forEach((node) => { node.open = true; });
    const mathRoots = [...document.querySelectorAll("math")];
    if (mathRoots.length > 0) {
      await document.fonts.load('16px "FPTR Latin Modern Math"', "F(α,G)∑{}");
    }
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const viewportWidth = document.documentElement.clientWidth;
    const blocks = [...document.querySelectorAll(".formula-block")];
    const errors = [];
    if (mathRoots.length > 0 && !document.fonts.check('16px "FPTR Latin Modern Math"')) {
      errors.push("bundled math font did not load");
    }
    const inconsistentMathTokens = [
      ...document.querySelectorAll("math, math mi, math mn, math mo, math mtext, math ms"),
    ].filter((node) => !getComputedStyle(node).fontFamily.includes("FPTR Latin Modern Math"));
    if (inconsistentMathTokens.length > 0) {
      errors.push(`${inconsistentMathTokens.length} MathML nodes do not use the bundled math font`);
    }
    if (document.documentElement.scrollWidth > viewportWidth + 1) {
      errors.push(`expanded equations overflow page: ${document.documentElement.scrollWidth} > ${viewportWidth}`);
    }
    const checkDelimiterScale = (root, label) => {
      [...root.querySelectorAll("mo")]
        .filter((node) => /^[()[\]{}|]$/.test(node.textContent.trim()))
        .forEach((node, index) => {
          const fontSize = parseFloat(getComputedStyle(node).fontSize);
          const height = node.getBoundingClientRect().height;
          if (fontSize > 0 && height / fontSize > 1.85) {
            errors.push(`${label}-delimiter-${index + 1}: delimiter is ${(
              height / fontSize
            ).toFixed(2)}em tall`);
          }
        });
    };
    blocks.forEach((block) => {
      const id = block.dataset.equation || block.id || "unknown";
      const math = block.querySelector('math[display="block"]');
      const annotation = math?.querySelector('annotation[encoding="application/x-tex"]');
      const number = block.querySelector(".equation-number");
      const rect = block.getBoundingClientRect();
      const mathRect = math?.getBoundingClientRect();
      if (!math) errors.push(`${id}: missing display MathML`);
      if (!annotation?.textContent.trim()) errors.push(`${id}: missing TeX annotation`);
      if (!math?.getAttribute("aria-label")) errors.push(`${id}: missing accessible label`);
      if (!mathRect || mathRect.width <= 0 || mathRect.height <= 0) errors.push(`${id}: MathML did not render`);
      if (math && parseFloat(getComputedStyle(math).fontSize) < 15.9) errors.push(`${id}: formula text below 16px`);
      if (block.tabIndex < 0 || block.dataset.scrollRegion !== "true") errors.push(`${id}: scroll region is not focusable`);
      if (rect.left < -1 || rect.right > viewportWidth + 1) errors.push(`${id}: formula container leaves viewport`);
      if (id !== "budget" && !number) errors.push(`${id}: missing equation number`);
      if (math) checkDelimiterScale(math, id);
    });
    [...document.querySelectorAll(".inline-math")].forEach((math, index) => {
      if (getComputedStyle(math).whiteSpace !== "nowrap") {
        errors.push(`inline-${index + 1}: inline MathML may break across lines`);
      }
      const tokens = [...math.children]
        .map((token) => token.getBoundingClientRect())
        .filter((rect) => rect.width > 0 || rect.height > 0);
      if (tokens.length > 1 && tokens.every((rect) => Math.abs(rect.left - tokens[0].left) < 1)) {
        errors.push(`inline-${index + 1}: inline MathML tokens collapsed into a vertical stack`);
      }
      checkDelimiterScale(math, `inline-${index + 1}`);
    });
    details.forEach((node, index) => { node.open = previous[index]; });
    return { count: blocks.length, errors };
  });
  assert.equal(result.count, route.equations || 0, `${route.name} has an unexpected number of display equations`);
  assert.deepEqual(result.errors, [], `${route.name} equation errors: ${result.errors.join("; ")}`);
}

async function runLiveDemo(browser, origin, {
  path: routePath,
  screenshot,
  viewport = { width: 390, height: 844 },
  stageId = "full",
  verifyLinearRerun = false
}) {
  const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
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
  assert.equal(await page.locator("#results").isHidden(), true, `${routePath} exposes results before a run`);
  assert.equal(await page.locator(".run-button:visible").count(), 1, `${routePath} must have one primary run action before results`);
  assert.equal(await page.locator("#scenarioSelect").inputValue(), "small-balanced", `${routePath} must recommend the small balanced scenario`);
  assert.equal(await page.locator("#deepAnalysis").count(), 1, `${routePath} must have one deep-analysis disclosure`);
  const budgetSlider = page.locator("#budgetSlider");
  assert.equal(await budgetSlider.getAttribute("type"), "range", `${routePath} does not use a linear budget control`);
  assert.equal(await budgetSlider.getAttribute("min"), "20", `${routePath} has the wrong minimum budget`);
  assert.equal(await budgetSlider.getAttribute("max"), "180", `${routePath} has the wrong maximum budget`);
  assert.equal(await budgetSlider.getAttribute("step"), "1", `${routePath} does not support 1 ms budget steps`);
  assert.equal(await budgetSlider.inputValue(), "87", `${routePath} does not start at the paper-default budget`);
  assert.equal((await page.locator("#budgetValue").textContent()).trim(), "87 ms", `${routePath} does not expose the current budget`);
  assert.ok((await budgetSlider.getAttribute("aria-valuetext")).includes("87 ms"), `${routePath} has no accessible budget value`);
  assert.equal(await page.locator("#budgetButtons").count(), 0, `${routePath} still exposes discrete budget buttons`);

  const stageButton = page.locator(`#stageButtons button[data-stage="${stageId}"]`);
  const stageLabel = (await stageButton.textContent()).trim();
  if (stageId !== "full") {
    await page.locator(".advanced-controls > summary").click();
    await stageButton.click();
    await page.locator(".advanced-controls > summary").click();
  }
  await page.locator("#runButton").click();
  await page.waitForFunction(() => !document.querySelector("#results")?.hidden && document.querySelectorAll("#comparisonBars .comparison-bar").length === 8, null, { timeout: 60000 });
  await page.waitForFunction(() => document.activeElement?.id === "resultTitle", null, { timeout: 5000 });
  assert.equal(await visible(page.locator("#results")), true, `${routePath} did not reveal results after a successful run`);
  assert.equal(await page.locator("#kpiGrid .kpi").count(), 3, `${routePath} does not show exactly three result summaries`);
  assert.equal(await page.locator("#comparisonBars .comparison-bar").count(), 8, `${routePath} does not show eight comparison bars`);
  assert.equal(await page.locator("#comparisonBody tr").count(), 8);
  assert.ok((await page.locator("#instanceSummary").textContent()).includes(stageLabel), `${routePath} omits the executed FPTR stage from its result summary`);
  const primaryLabel = (await page.locator("#comparisonBars .comparison-bar.primary .comparison-bar-label").textContent()).trim();
  assert.equal(primaryLabel, stageId === "full" ? "FPTR" : `FPTR · ${stageLabel}`, `${routePath} mislabels the selected FPTR stage`);
  const positions = await page.evaluate(() => {
    const header = document.querySelector(".site-header").getBoundingClientRect();
    const results = document.querySelector("#results").getBoundingClientRect();
    return { headerBottom: header.bottom, resultsTop: results.top };
  });
  assert.ok(positions.resultsTop >= positions.headerBottom + 8, `${routePath} results are hidden behind the sticky header`);
  assert.equal(await page.locator("#deepAnalysis").getAttribute("open"), null, `${routePath} opens deep analysis by default`);
  assert.equal(await page.locator(".analysis-tabs .tab").count(), 4, `${routePath} must provide four analysis views`);
  assert.equal(await page.locator("#rawOutput").textContent(), "", `${routePath} eagerly renders raw stdout`);
  await assertLoadedResources(page, { name: routePath }, errors);
  await page.screenshot({ path: path.join(screenshots, screenshot), fullPage: true });
  await page.locator("#deepAnalysis > summary").click();
  const stageChart = page.locator("#stageChart svg");
  assert.ok(await stageChart.getAttribute("aria-label"), `${routePath} stage chart has no localized accessible name`);
  const stageFontSizes = await stageChart.locator("text").evaluateAll(
    (nodes) => nodes.map((node) => Number.parseFloat(getComputedStyle(node).fontSize))
  );
  assert.ok(Math.min(...stageFontSizes) >= 11, `${routePath} stage chart text is smaller than 11px`);
  await page.locator("#allocationTabButton").click();
  assert.equal(await page.locator(".share-legend > span").count(), 4, `${routePath} does not label all four sharing levels`);
  await page.locator("#recordTabButton").click();
  assert.equal(await page.locator("#rawOutput").textContent(), "", `${routePath} renders raw stdout before its disclosure opens`);
  await page.locator("#rawDetails > summary").click();
  assert.ok((await page.locator("#rawOutput").textContent()).length > 0, `${routePath} does not render raw stdout on demand`);
  const postRunWidth = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
  assert.ok(postRunWidth.scroll <= postRunWidth.client + 1, `${routePath} overflows after run: ${postRunWidth.scroll} > ${postRunWidth.client}`);
  await budgetSlider.evaluate((node) => {
    node.value = "73";
    node.dispatchEvent(new Event("input", { bubbles: true }));
  });
  assert.equal(await budgetSlider.inputValue(), "73", `${routePath} does not accept an intermediate linear budget`);
  assert.equal((await page.locator("#budgetValue").textContent()).trim(), "73 ms", `${routePath} does not update the budget readout`);
  assert.equal(await budgetSlider.getAttribute("aria-valuetext"), "73 ms", `${routePath} does not update the accessible budget value`);
  assert.equal(await page.locator("#results").getAttribute("class").then((value) => value.includes("is-stale")), true, `${routePath} does not mark old results as stale`);
  assert.equal(await visible(page.locator("#staleBanner")), true, `${routePath} does not expose the stale-result warning`);
  assert.equal(await page.locator("#downloadButton").isDisabled(), true, `${routePath} permits exporting stale results`);
  await assertLayout(page, { name: `${routePath}-stale`, demo: true }, viewport);
  if (verifyLinearRerun) {
    await page.locator("#rerunButton").click();
    await page.waitForFunction(() => {
      const results = document.querySelector("#results");
      const summary = document.querySelector("#instanceSummary")?.textContent || "";
      return !results?.classList.contains("is-stale") && summary.includes("73 ms");
    }, null, { timeout: 60000 });
    assert.equal(await visible(page.locator("#staleBanner")), false, `${routePath} keeps the stale warning after a 73 ms rerun`);
    assert.equal(await page.locator("#downloadButton").isEnabled(), true, `${routePath} does not enable export after a 73 ms rerun`);
    assert.ok((await page.locator("#instanceSummary").textContent()).includes("73 ms"), `${routePath} did not run all methods at the intermediate budget`);
  }
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
        await assertEquations(page, route);
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
        await page.screenshot({ path: path.join(folder, `${route.name}.png`), fullPage: true });
        assert.deepEqual(pageErrors, [], `browser errors on ${route.name} at ${viewport.width}px: ${pageErrors.join("; ")}`);
        await page.close();
        routeChecks += 1;
      }
      await context.close();
    }

    await runLiveDemo(browser, origin, {
      path: "/demo/",
      screenshot: "demo-live-mobile.png",
      verifyLinearRerun: true
    });
    await runLiveDemo(browser, origin, {
      path: "/en/demo/",
      screenshot: "demo-live-mobile-en.png",
      stageId: "base"
    });
    await runLiveDemo(browser, origin, {
      path: "/demo/",
      screenshot: "demo-live-desktop.png",
      viewport: { width: 1440, height: 1000 }
    });

    process.stdout.write(`Browser layout checks passed for ${routeChecks} route/viewport combinations, no-JS navigation, and three eight-method live Demo runs.\n`);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
