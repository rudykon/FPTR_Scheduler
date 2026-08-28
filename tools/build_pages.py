#!/usr/bin/env python3
"""Render static Chinese and English FPTR Pages from checked-in HTML templates."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

PAGES = (
    Path("index.html"),
    Path("problem/index.html"),
    Path("method/index.html"),
    Path("evidence/index.html"),
    Path("reproduce/index.html"),
    Path("demo/index.html"),
)
SITE_ORIGIN = "https://rudykon.github.io/FPTR_Scheduler"
SITE_PATH = "/FPTR_Scheduler"


def page_slug(relative: Path) -> str:
    return "" if relative == Path("index.html") else relative.parent.as_posix()


def public_url(relative: Path, locale: str | None) -> str:
    prefix = "" if locale in (None, "zh") else f"/{locale}"
    slug = page_slug(relative)
    suffix = f"/{slug}" if slug else ""
    return f"{SITE_ORIGIN}{prefix}{suffix}/"


def route_path(relative: Path, locale: str) -> str:
    slug = page_slug(relative)
    suffix = f"/{slug}/" if slug else "/"
    locale_prefix = "" if locale == "zh" else f"/{locale}"
    return f"{SITE_PATH}{locale_prefix}{suffix}"


def replace_i18n(text: str, strings: dict[str, str]) -> str:
    pattern = re.compile(
        r'(<(?P<tag>[a-z][\w-]*)\b[^>]*\bdata-i18n="(?P<key>[^"]+)"[^>]*>)'
        r'(?P<body>.*?)'
        r'(</(?P=tag)>)',
        re.IGNORECASE | re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        value = strings.get(match.group("key"))
        if value is None:
            return match.group(0)
        return f"{match.group(1)}{html.escape(value)}{match.group(5)}"

    return pattern.sub(replace, text)


def normalized_fallback(value: str) -> str:
    """Return the text that a reader receives from an HTML fallback."""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split())


def validate_template_fallbacks(relative: Path, source: str, zh: dict[str, str]) -> None:
    """Keep checked-in Chinese fallbacks identical to the canonical catalog."""
    text_pattern = re.compile(
        r'<(?P<tag>[a-z][\w-]*)\b[^>]*\bdata-i18n="(?P<key>[^"]+)"[^>]*>'
        r'(?P<body>.*?)'
        r'</(?P=tag)>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in text_pattern.finditer(source):
        key = match.group("key")
        fallback = normalized_fallback(match.group("body"))
        expected = normalized_fallback(zh[key])
        if fallback != expected:
            raise SystemExit(
                f"{relative}: HTML fallback differs from zh.json for {key}: "
                f"{fallback!r} != {expected!r}"
            )

    for data_name, attr_name in (("data-i18n-alt", "alt"), ("data-i18n-aria", "aria-label")):
        tag_pattern = re.compile(
            rf'<[a-z][\w-]*\b(?P<attrs>[^>]*\b{data_name}="(?P<key>[^"]+)"[^>]*)>',
            re.IGNORECASE,
        )
        for match in tag_pattern.finditer(source):
            key = match.group("key")
            attr = re.search(rf'\b{attr_name}="([^"]*)"', match.group("attrs"))
            fallback = normalized_fallback(attr.group(1) if attr else "")
            expected = normalized_fallback(zh[key])
            if fallback != expected:
                raise SystemExit(
                    f"{relative}: {attr_name} fallback differs from zh.json for {key}: "
                    f"{fallback!r} != {expected!r}"
                )


def replace_attribute_i18n(text: str, strings: dict[str, str], data_name: str, attr_name: str) -> str:
    pattern = re.compile(
        rf'<(?P<tag>[a-z][\w-]*)\b(?P<attrs>[^>]*\b{re.escape(data_name)}="(?P<key>[^"]+)"[^>]*)>',
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        value = strings.get(match.group("key"))
        if value is None:
            return match.group(0)
        attrs = match.group("attrs")
        escaped = html.escape(value, quote=True)
        attr_pattern = re.compile(rf'\b{re.escape(attr_name)}="[^"]*"')
        if attr_pattern.search(attrs):
            attrs = attr_pattern.sub(f'{attr_name}="{escaped}"', attrs, count=1)
        else:
            attrs += f' {attr_name}="{escaped}"'
        return f'<{match.group("tag")}{attrs}>'

    return pattern.sub(replace, text)


def metadata_key(source: str, name: str, fallback: str) -> str:
    match = re.search(rf'<body\b[^>]*\bdata-{re.escape(name)}-key="([^"]+)"', source)
    return match.group(1) if match else fallback


def replace_meta_content(source: str, selector: str, value: str) -> str:
    escaped = html.escape(value, quote=True)
    pattern = re.compile(
        rf'(<meta\b(?=[^>]*{selector})[^>]*\bcontent=")[^"]*(")',
        re.IGNORECASE,
    )
    return pattern.sub(rf'\g<1>{escaped}\2', source, count=1)


def replace_shared_paths(source: str, relative: Path) -> str:
    output_depth = len(relative.parent.parts) + 1
    root_prefix = "../" * output_depth
    shared = re.compile(r'(?P<quote>["\'])(?:\.\.?/)+(?:assets|images|appendices)/')

    def shared_replacement(match: re.Match[str]) -> str:
        token = match.group(0)[1:]
        leaf = re.search(r'(assets|images|appendices)/', token)
        assert leaf
        return match.group("quote") + root_prefix + token[leaf.start():]

    source = shared.sub(shared_replacement, source)
    if relative == Path("demo/index.html"):
        demo_prefix = root_prefix + "demo/"
        source = re.sub(
            r'(?P<quote>["\'])\./(?P<file>demo\.css|runtime\.js|app\.js|wasm/[^"\']+)',
            lambda match: match.group("quote") + demo_prefix + match.group("file"),
            source,
        )
    return source


def render_page(template: str, relative: Path, locale: str, strings: dict[str, str], localized: bool) -> str:
    output = replace_i18n(template, strings)
    output = replace_attribute_i18n(output, strings, "data-i18n-alt", "alt")
    output = replace_attribute_i18n(output, strings, "data-i18n-aria", "aria-label")
    lang = "zh-CN" if locale == "zh" else "en"
    output = re.sub(r'<html\b[^>]*\blang="[^"]+"', f'<html lang="{lang}"', output, count=1)

    title = strings[metadata_key(template, "title", "title")]
    description = strings[metadata_key(template, "description", "description")]
    output = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", output, count=1, flags=re.DOTALL)
    output = replace_meta_content(output, r'name="description"', description)
    output = replace_meta_content(output, r'property="og:title"', title)
    output = replace_meta_content(output, r'property="og:description"', description)

    url = public_url(relative, locale if localized else None)
    output = re.sub(r'(<link\b[^>]*\brel="canonical"[^>]*\bhref=")[^"]*(")', rf'\g<1>{url}\2', output, count=1)
    output = replace_meta_content(output, r'property="og:url"', url)

    alternates = (
        f'    <link rel="alternate" hreflang="zh-CN" href="{public_url(relative, None)}" />\n'
        f'    <link rel="alternate" hreflang="en" href="{public_url(relative, "en")}" />\n'
        f'    <link rel="alternate" hreflang="x-default" href="{public_url(relative, None)}" />'
    )
    output = re.sub(r'(\s*<link\b[^>]*\brel="canonical"[^>]*>)', rf'\1\n{alternates}', output, count=1)

    language_aria = html.escape(strings["languageAria"], quote=True)
    switch = (
        f'<div class="language-switch" aria-label="{language_aria}" data-i18n-aria="languageAria">'
        f'<a href="{route_path(relative, "zh")}" data-locale="zh"'
        f'{" class=\"active\" aria-current=\"page\"" if locale == "zh" else ""}>中</a>'
        f'<a href="{route_path(relative, "en")}" data-locale="en" lang="en"'
        f'{" class=\"active\" aria-current=\"page\"" if locale == "en" else ""}>EN</a>'
        '</div>'
    )
    output = re.sub(
        r'<div class="language-switch"[^>]*>.*?</div>',
        switch,
        output,
        count=1,
        flags=re.DOTALL,
    )
    if localized:
        output = replace_shared_paths(output, relative)
    return output


def referenced_keys(source: str) -> set[str]:
    keys = set(re.findall(r'data-i18n(?:-alt|-aria)?="([^"]+)"', source))
    keys.add(metadata_key(source, "title", "title"))
    keys.add(metadata_key(source, "description", "description"))
    return keys


def build(source_dir: Path, output_dir: Path, prune_unused: bool = False) -> None:
    content_paths = {locale: source_dir / "content" / f"{locale}.json" for locale in ("zh", "en")}
    content = {
        locale: json.loads(path.read_text(encoding="utf-8"))
        for locale, path in content_paths.items()
    }
    templates = {relative: (source_dir / relative).read_text(encoding="utf-8") for relative in PAGES}
    keys = set().union(*(referenced_keys(source) for source in templates.values()))
    if prune_unused:
        for locale, strings in content.items():
            content[locale] = {key: value for key, value in strings.items() if key in keys}
            content_paths[locale].write_text(
                json.dumps(content[locale], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    for locale, strings in content.items():
        missing = sorted(keys - strings.keys())
        if missing:
            raise SystemExit(f"{locale}.json is missing translation keys: {', '.join(missing)}")
        unused = sorted(strings.keys() - keys)
        if unused:
            raise SystemExit(
                f"{locale}.json has unused translation keys: {', '.join(unused)}. "
                "Run build_pages.py once with --prune-unused."
            )

    for relative, template in templates.items():
        validate_template_fallbacks(relative, template, content["zh"])

    for relative, template in templates.items():
        root_destination = output_dir / relative
        root_destination.parent.mkdir(parents=True, exist_ok=True)
        root_destination.write_text(
            render_page(template, relative, "zh", content["zh"], localized=False),
            encoding="utf-8",
        )
        for locale in ("en",):
            destination = output_dir / locale / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                render_page(template, relative, locale, content[locale], localized=True),
                encoding="utf-8",
            )
    shutil.rmtree(output_dir / "zh", ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("docs"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--prune-unused",
        action="store_true",
        help="remove translation entries that no checked-in page references",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(args.source.resolve(), args.output.resolve(), prune_unused=args.prune_unused)
