from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from tools.build_web_figure_fallbacks import validate_native_svg


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class I18nParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str | None] = []
        self.values: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        key = dict(attrs).get("data-i18n")
        self.stack.append(key)
        if key:
            self.values.setdefault(key, [])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        for key in reversed(self.stack):
            if key:
                self.values[key].append(data)
                break

    def flattened(self) -> dict[str, str]:
        return {key: " ".join("".join(parts).split()) for key, parts in self.values.items()}


class PagesContractTests(unittest.TestCase):
    def test_reproduction_shell_blocks_are_syntax_valid(self) -> None:
        source = (DOCS / "reproduce/index.html").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\s\+\s")
        blocks = re.findall(
            r"<pre\b[^>]*data-shell[^>]*>\s*<code\b[^>]*>(.*?)</code>\s*</pre>",
            source,
            flags=re.DOTALL,
        )
        self.assertGreaterEqual(len(blocks), 4)
        self.assertEqual(source.count('class="copy-code"'), len(blocks))
        self.assertEqual(source.count('class="code-shell"'), len(blocks))
        self.assertEqual(source.count('tabindex="0"'), len(blocks))
        for block in blocks:
            command = html.unescape(block)
            result = subprocess.run(
                ["bash", "-n"],
                input=command,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        for required in (
            "src/scheduler.cpp src/core.cpp",
            "space/data/cases/small-balanced.in",
            "--stage full",
            "--budget-ms 87",
            "--samples /tmp/fptr-samples",
            "--output-dir /tmp/fptr-output",
        ):
            self.assertIn(required, source)

    def test_native_sample_closes_compile_run_validate_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scheduler = tmp_path / "scheduler"
            samples = tmp_path / "samples"
            outputs = tmp_path / "outputs"
            samples.mkdir()
            outputs.mkdir()
            subprocess.run(
                [
                    "g++", "-std=c++17", "-O2",
                    str(ROOT / "src/scheduler.cpp"),
                    str(ROOT / "src/core.cpp"),
                    "-o", str(scheduler),
                ],
                check=True,
                timeout=60,
            )
            sample = samples / "small-balanced.in"
            shutil.copy2(ROOT / "space/data/cases/small-balanced.in", sample)
            with sample.open("rb") as stdin, (outputs / "small-balanced.out").open("wb") as stdout:
                subprocess.run(
                    [str(scheduler), "--stage", "full", "--budget-ms", "87", "--trace"],
                    stdin=stdin,
                    stdout=stdout,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=20,
                )
            subprocess.run(
                [
                    "python3", str(ROOT / "tools/scheduler_validator.py"),
                    "--samples", str(samples),
                    "--output-dir", str(outputs),
                ],
                check=True,
                timeout=20,
            )

    def test_static_bilingual_build_has_matching_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            subprocess.run(
                [
                    "python3", str(ROOT / "tools/build_pages.py"),
                    "--source", str(DOCS),
                    "--output", str(output),
                ],
                check=True,
            )
            for page in ("index.html", "problem/index.html", "method/index.html", "evidence/index.html", "reproduce/index.html", "demo/index.html"):
                self.assertTrue((output / page).is_file(), f"missing root/{page}")
                self.assertTrue((output / "en" / page).is_file(), f"missing en/{page}")
            self.assertFalse((output / "zh").exists())
            root_html = (output / "index.html").read_text(encoding="utf-8")
            en_html = (output / "en/index.html").read_text(encoding="utf-8")
            root_parser, en_parser = I18nParser(), I18nParser()
            root_parser.feed(root_html)
            en_parser.feed(en_html)
            self.assertEqual(root_parser.flattened()["paperTitle"], "FPTR Scheduler")
            self.assertNotEqual(root_parser.flattened()["homeSubtitle"], en_parser.flattened()["homeSubtitle"])
            self.assertIn('<html lang="zh-CN">', root_html)
            self.assertIn('<html lang="en">', en_html)
            self.assertIn('rel="canonical" href="https://rudykon.github.io/FPTR_Scheduler/"', root_html)
            self.assertIn('rel="canonical" href="https://rudykon.github.io/FPTR_Scheduler/en/"', en_html)
            self.assertIn('hreflang="zh-CN" href="https://rudykon.github.io/FPTR_Scheduler/"', root_html)
            self.assertIn('hreflang="x-default" href="https://rudykon.github.io/FPTR_Scheduler/"', root_html)
            self.assertIn('href="/FPTR_Scheduler/" data-locale="zh"', en_html)
            self.assertIn('href="../../assets/site.css"', (output / "en/method/index.html").read_text(encoding="utf-8"))
            demo_en = (output / "en/demo/index.html").read_text(encoding="utf-8")
            self.assertIn('src="../../demo/app.js"', demo_en)
            self.assertIn("Live Scheduling Demo", demo_en)
            self.assertNotIn("applyLocale", (DOCS / "assets/site.js").read_text(encoding="utf-8"))

    def test_information_hierarchy_and_research_questions(self) -> None:
        home = (DOCS / "index.html").read_text(encoding="utf-8")
        for forbidden in (
            "论文伴读站",
            "结果按研究问题展开，而不是堆成一张图表墙",
            "按你的问题进入，不必把一个长页面拉到底",
            "一份能被检查的研究代码，而不是黑盒演示",
        ):
            self.assertNotIn(forbidden, home)
        self.assertEqual(home.count('class="summary-card '), 3)
        self.assertEqual(len(re.findall(r'<a class="summary-card [^"]+" href="[^"]+">', home)), 3)
        self.assertNotIn('class="reading-grid"', home)
        self.assertNotIn('class="home-reading"', home)
        self.assertEqual(len(re.findall(r"<h2\b", home)), 0)
        for key in ("constraintCountLabel", "gateCountLabel", "beamFirstGainLabel"):
            self.assertIn(f'data-i18n="{key}"', home)

        evidence = (DOCS / "evidence/index.html").read_text(encoding="utf-8")
        for rq in ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5"):
            self.assertIn(rq, evidence)
        for anchor in ("quality", "deadline", "cg-stress", "baselines", "exact", "limits"):
            self.assertIn(f'id="{anchor}"', evidence)
        self.assertEqual(evidence.count('class="evidence-highlights"'), 1)
        highlights = re.search(r'<div class="evidence-highlights"[^>]*>(.*?)</div>', evidence, re.DOTALL)
        self.assertIsNotNone(highlights)
        self.assertEqual(highlights.group(1).count("<article>"), 3)
        self.assertEqual(evidence.count('class="secondary-figure"'), 2)
        self.assertEqual(evidence.count('class="figure-size-link"'), 6)
        self.assertNotIn('class="terms terms-desktop"', evidence)
        self.assertNotIn('class="terms-mobile"', evidence)
        for question in range(1, 6):
            self.assertIn(f'data-i18n="rq{question}Question"', evidence)
        for key in (
            "stageGainAlt",
            "scenarioGainAlt",
            "runtimeAlt",
            "budgetAlt",
            "cgStressAlt",
            "optimalityAlt",
        ):
            self.assertIn(f'data-i18n-alt="{key}"', evidence)
        self.assertNotIn(".svg", evidence)
        self.assertNotIn("<picture", evidence)
        exact = re.search(r'<div class="exact-metrics">(.*?)</div>', evidence, re.DOTALL)
        self.assertIsNotNone(exact)
        for value in ("8 / 12", "0%", "3.19%", "25%"):
            self.assertIn(value, exact.group(1))

        method = (DOCS / "method/index.html").read_text(encoding="utf-8")
        timeline = re.search(r'<div class="method-timeline">(.*?)</div>', method, re.DOTALL)
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline.group(1).count('class="stage'), 6)
        self.assertIn('data-i18n-aria="budgetBAria"', method)
        self.assertIn('data-i18n-aria="budgetDAria"', method)
        for key in ("invariantSummary", "topSSummary", "methodLimitSummary", "proofDetails", "scopeDetails"):
            self.assertIn(f'data-i18n="{key}"', method)

        problem = (DOCS / "problem/index.html").read_text(encoding="utf-8")
        self.assertIn('class="key-symbols"', problem)
        self.assertIn('class="symbol-details"', problem)

        reproduce = (DOCS / "reproduce/index.html").read_text(encoding="utf-8")
        for legacy in ("8,610", 'class="audit-flow"', 'class="repo-map"', 'class="repo-tree"'):
            self.assertNotIn(legacy, reproduce)
        self.assertIn('data-i18n="expectedResultTitle"', reproduce)
        self.assertIn('data-i18n="fullExperimentTitle"', reproduce)

        zh = json.loads((DOCS / "content/zh.json").read_text(encoding="utf-8"))
        en = json.loads((DOCS / "content/en.json").read_text(encoding="utf-8"))
        self.assertEqual(set(zh), set(en))
        pages = [DOCS / "index.html", *(DOCS / name / "index.html" for name in ("problem", "method", "evidence", "reproduce", "demo"))]
        for page in pages:
            source = page.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"<h1\b", source)), 1, page)
            self.assertLessEqual(len(re.findall(r"<h2\b", source)), 7, page)
            heading_keys = re.findall(r'<h[12]\b[^>]*data-i18n="([^"]+)"', source)
            for key in heading_keys:
                self.assertLessEqual(len(re.sub(r"\s+", "", zh[key])), 18, f"Chinese heading {key} is too long")
                self.assertLessEqual(len(en[key]), 32, f"English heading {key} is too long")
            paragraph_values = [
                zh[key]
                for key in re.findall(r'<p\b[^>]*data-i18n="([^"]+)"', source)
                if len(zh[key]) >= 20
            ]
            duplicate_paragraphs = sorted({value for value in paragraph_values if paragraph_values.count(value) > 1})
            self.assertEqual(duplicate_paragraphs, [], f"duplicate long paragraphs in {page}")
            for details in re.findall(r"<details\b.*?</details>", source, flags=re.DOTALL):
                self.assertIn("<summary", details, f"details without summary in {page}")
            for image in re.findall(r"<img\b[^>]*>", source, flags=re.DOTALL):
                self.assertRegex(image, r'\balt="[^"]*"', f"image without alt in {page}")

    def test_acm_equation_contract(self) -> None:
        problem = (DOCS / "problem/index.html").read_text(encoding="utf-8")
        method = (DOCS / "method/index.html").read_text(encoding="utf-8")
        evidence = (DOCS / "evidence/index.html").read_text(encoding="utf-8")
        sources = problem + method + evidence

        for number in range(1, 8):
            self.assertEqual(problem.count(f'data-equation="{number}"'), 1)
            self.assertEqual(problem.count(f'aria-hidden="true">({number})</span>'), 1)
        for number in (8, 9):
            self.assertEqual(method.count(f'data-equation="{number}"'), 1)
            self.assertEqual(method.count(f'aria-hidden="true">({number})</span>'), 1)
        self.assertEqual(method.count('data-equation="budget"'), 1)
        self.assertEqual(evidence.count('data-equation="A1"'), 1)
        self.assertIn('aria-hidden="true">(A1)</span>', evidence)

        display_math_count = sources.count('<math display="block"')
        formula_count = sources.count('class="formula-block')
        formula_openers = re.findall(r'<div class="formula-block[^"]*"[^>]*>', sources)
        display_openers = re.findall(r'<math display="block"[^>]*>', sources)
        self.assertEqual(display_math_count, formula_count)
        self.assertEqual(len(formula_openers), formula_count)
        self.assertTrue(all('tabindex="0"' in opener for opener in formula_openers))
        self.assertTrue(all('aria-label=' in opener and 'data-i18n-aria=' in opener for opener in display_openers))
        self.assertEqual(sources.count('<annotation encoding="application/x-tex">'), display_math_count)
        self.assertEqual(sources.count('data-equation='), display_math_count)
        self.assertEqual(sources.count('class="equation-row"'), display_math_count)
        self.assertEqual(sources.count('<math display="block" aria-label='), display_math_count)

        for required in (
            '<munder><mo>∑</mo>',
            '<munderover><mo>⋃</mo>',
            '<mfrac>',
            '<mtable',
            'mathvariant="normal">min',
            'mathvariant="normal">max',
            '<mtext>ms</mtext>',
            '\\tau_{\\mathrm{done}}',
            '\\widetilde F_{i,m}',
        ):
            self.assertIn(required, sources)
        for legacy in (
            'F(α,G) = Σ',
            't<sub>done</sub>',
            '<code>V(C)',
            '<code>F(C)',
            'B=87 ms',
            'D=100 ms',
        ):
            self.assertNotIn(legacy, problem + method)

        site_css = (DOCS / "assets/site.css").read_text(encoding="utf-8")
        for required in (
            '--math:',
            '.formula-block math',
            '.equation-row',
            '.equation-number',
            'grid-template-columns: minmax(0, 1fr) 3rem',
            'overflow-x: auto',
        ):
            self.assertIn(required, site_css)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            subprocess.run(
                ["python3", str(ROOT / "tools/build_pages.py"), "--source", str(DOCS), "--output", str(output)],
                check=True,
            )
            en_problem = (output / "en/problem/index.html").read_text(encoding="utf-8")
            en_method = (output / "en/method/index.html").read_text(encoding="utf-8")
            self.assertIn('aria-label="Equation 6:', en_problem)
            self.assertIn('aria-label="Equation 9:', en_method)
            self.assertEqual(en_problem.count('<annotation encoding="application/x-tex">'), 7)
            self.assertEqual(en_method.count('<annotation encoding="application/x-tex">'), 3)

    def test_mobile_and_demo_css_contract(self) -> None:
        site_css = (DOCS / "assets/site.css").read_text(encoding="utf-8")
        demo_css = (DOCS / "demo/demo.css").read_text(encoding="utf-8")
        compact_demo = re.sub(r"\s+", " ", demo_css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", compact_demo)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", compact_demo)
        self.assertIn(".kpi:nth-child(3) { grid-column: 1 / -1; }", compact_demo)
        self.assertIn(".kpi span { letter-spacing: 0; text-transform: none; }", compact_demo)
        self.assertIn("min-width: 760px", compact_demo)
        self.assertRegex(
            compact_demo,
            r"main, \.demo-app, \.demo-workspace, \.control-panel, \.results-section, \.comparison-panel, \.advanced-results, \.advanced-detail \{ min-width: 0; max-width: 100%; \}",
        )
        self.assertNotRegex(site_css + demo_css, r"body\s*\{[^}]*overflow(?:-x)?\s*:\s*hidden")
        self.assertIn("--demo-body: 1rem", demo_css)
        self.assertIn("--demo-meta: .875rem", demo_css)
        self.assertIn("padding: 1.6rem 0 1.5rem", site_css)
        self.assertIn("clamp(2.1rem, 3.4vw, 3rem)", site_css)
        self.assertIn(".js .main-nav.is-open", site_css)
        self.assertIn(".js .nav-toggle", site_css)
        self.assertIn(".key-symbols", site_css)
        self.assertIn(".evidence-highlights", site_css)
        self.assertNotIn(".terms-mobile", site_css)
        self.assertNotIn(".terms-desktop", site_css)
        self.assertIn(".rq-nav.is-open", site_css)
        self.assertIn('html[lang="en"] .home-hero h1', site_css)
        self.assertIn('html[lang="en"] .page-hero h1', site_css)
        self.assertIn('html[lang="en"] .page-hero p:last-of-type', site_css)

        site_js = (DOCS / "assets/site.js").read_text(encoding="utf-8")
        for behavior in ("nav-toggle", "rq-toggle", "copy-code", "dataset.scrollRegion"):
            self.assertIn(behavior, site_js)
        for behavior in ("restoreNavFocus", "restoreRqFocus", "navToggle.focus()", "rqToggle.focus()"):
            self.assertIn(behavior, site_js)

        pages = [DOCS / "index.html", *(DOCS / name / "index.html" for name in ("problem", "method", "evidence", "reproduce", "demo"))]
        for page in pages:
            source = page.read_text(encoding="utf-8")
            self.assertIn('document.documentElement.classList.add("js")', source)
            self.assertIn('class="nav-toggle"', source)
            self.assertIn('id="mainNav"', source)
            self.assertNotIn('/zh/', source)
        evidence = (DOCS / "evidence/index.html").read_text(encoding="utf-8")
        self.assertIn('class="rq-toggle"', evidence)
        self.assertIn('id="rqNav"', evidence)

    def test_web_figure_manifest_is_current(self) -> None:
        subprocess.run(
            ["python3", str(ROOT / "tools/build_web_figure_fallbacks.py"), "--check"],
            cwd=ROOT,
            check=True,
        )
        payload = json.loads((DOCS / "evidence/figure-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["profile"], "audited-png-fallback")
        self.assertEqual(
            payload["pending_artifacts"],
            [
                "panel-label-free native web SVG/PNG",
                "mobile-specific large-type PNG",
            ],
        )
        self.assertEqual(len(payload["figures"]), 6)
        for name in payload["figures"]:
            self.assertTrue((DOCS / "images" / f"{name}.png").is_file())
            self.assertFalse((DOCS / "images" / f"{name}.svg").exists())

    def test_web_figure_profile_is_large_type_and_panel_label_free(self) -> None:
        source = (ROOT / "experiments/plot_paper_results.py").read_text(encoding="utf-8")
        self.assertIn("FIGURE_WIDTH_IN = 8.5", source)
        self.assertIn("BODY_FONT_PT = 11.5", source)
        self.assertIn("SMALL_FONT_PT = 11.0", source)
        self.assertIn('if ACTIVE_PROFILE != "paper":', source)
        self.assertIn('"panel_labels": False', source)
        self.assertIn('"shared_legend": False', source)
        web_builder = source[source.index("def build_web_figures("):source.index("def split_main()")]
        self.assertNotIn("panel_label(", web_builder)

    def test_svg_integrity_rejects_raster_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg = Path(tmp) / "figure.svg"
            svg.write_text('<svg><image href="figure.png" /></svg>', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "embeds a raster image"):
                validate_native_svg(svg)
            svg.write_text('<svg><path d="M0 0L1 1" /><text>FPTR</text></svg>', encoding="utf-8")
            validate_native_svg(svg)

    def test_pages_workflow_runs_browser_regression(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        for required in (
            "playwright@1.55.0",
            "tests/browser_pages.js _site artifacts/browser",
            "pages-browser-screenshots",
            "npx playwright install --with-deps chromium",
        ):
            self.assertIn(required, workflow)
        browser_test = (ROOT / "tests/browser_pages.js").read_text(encoding="utf-8")
        for required in (
            "{ width: 360, height: 800 }",
            "{ width: 375, height: 812 }",
            'path: "/en/problem/"',
            'path: "/en/demo/"',
            "image.naturalWidth === 0",
            "response.status() >= 400",
            "javaScriptEnabled: false",
            "All live runs validated",
        ):
            self.assertIn(required, browser_test)


if __name__ == "__main__":
    unittest.main()
