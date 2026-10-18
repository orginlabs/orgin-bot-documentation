#!/usr/bin/env python3
"""Dependency-free checks for the Orgin documentation repository."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []


def error(message: str) -> None:
    ERRORS.append(message)
    print(f"ERROR: {message}")


def without_fenced_code(text: str) -> str:
    text = re.sub(r"(?ms)^```[^\n]*\n.*?^```[ \t]*$", "", text)
    return re.sub(r"`+[^`]*`+", "", text)


def check_markdown_links() -> int:
    count = 0
    markdown_files = sorted(path for path in ROOT.rglob("*.md") if ".git" not in path.parts)
    link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        prose = without_fenced_code(text)
        for raw in link_pattern.findall(prose):
            target = raw.strip().split()[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            relative = target.split("#", 1)[0].split("?", 1)[0]
            if not relative:
                continue
            count += 1
            if not (path.parent / relative).exists():
                error(f"broken relative Markdown link: {path.relative_to(ROOT)} -> {target}")
        for image_src in re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', prose, flags=re.I):
            if image_src.startswith(("http://", "https://", "data:")):
                continue
            count += 1
            if not (path.parent / image_src).exists():
                error(f"missing local Markdown image: {path.relative_to(ROOT)} -> {image_src}")
    return count


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "img" and attributes.get("src") and not str(attributes["src"]).startswith(("http://", "https://", "data:")):
            target = (ROOT / str(attributes["src"])).resolve()
            if not target.exists():
                self.errors.append(f"missing local image: {attributes['src']}")
        if tag == "a" and attributes.get("href") and str(attributes["href"]).startswith("#"):
            pass


def check_mermaid_fences() -> int:
    count = 0
    for path in sorted(path for path in ROOT.rglob("*.md") if ".git" not in path.parts):
        text = path.read_text(encoding="utf-8")
        matches = list(re.finditer(r"```mermaid\s*\n(.*?)\n```", text, flags=re.S | re.I))
        count += len(matches)
        openers = re.findall(r"(?im)^```mermaid\s*$", text)
        if len(openers) != len(matches):
            error(f"unclosed Mermaid code fence: {path.relative_to(ROOT)}")
        for match in matches:
            body = match.group(1).strip()
            if not body or not re.match(r"^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|mindmap|timeline)\b", body):
                error(f"invalid or empty Mermaid diagram: {path.relative_to(ROOT)}")
    return count


def check_site() -> None:
    path = ROOT / "index.html"
    if not path.exists():
        error("index.html is missing")
        return
    parser = SiteParser()
    try:
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
    except Exception as exc:  # HTMLParser is tolerant, but report decoder/parser errors.
        error(f"could not parse index.html: {exc}")
    for issue in parser.errors:
        error(f"index.html: {issue}")
    sitemap = ROOT / "sitemap.xml"
    if sitemap.exists():
        try:
            ET.parse(sitemap)
        except ET.ParseError as exc:
            error(f"invalid sitemap.xml: {exc}")


def main() -> int:
    links = check_markdown_links()
    diagrams = check_mermaid_fences()
    check_site()
    if ERRORS:
        print(f"\n{len(ERRORS)} validation error(s).")
        return 1
    print(f"Validation passed: {links} local Markdown links and {diagrams} Mermaid diagram(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
