"""Offline HTML diagnostics and explicit local snapshot saving; no HTTP."""

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

KEYWORDS = ("承認", "同意", "確認", "利用規約", "agreement", "consent")


@dataclass(frozen=True)
class HtmlDiagnostics:
    title: str | None
    meta_refresh: bool
    form_count: int
    link_count: int
    script_count: int
    iframe_count: int
    submit_count: int
    has_password_input: bool
    has_checkbox: bool
    approval_keywords: tuple[str, ...]

    @property
    def possible_approval_page(self) -> bool:
        return bool(self.approval_keywords)


def diagnose_html(html: str) -> HtmlDiagnostics:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    inputs = soup.find_all("input")
    submit_count = sum(str(tag.get("type", "")).lower() in ("submit", "image") for tag in inputs)
    submit_count += sum(str(tag.get("type", "submit")).lower() == "submit" for tag in soup.find_all("button"))
    counts = {name: len(soup.find_all(name)) for name in ("form", "script", "iframe")}
    refresh = any(str(tag.get("http-equiv", "")).lower() == "refresh" for tag in soup.find_all("meta"))
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True).casefold()
    return HtmlDiagnostics(
        title=title, meta_refresh=refresh, form_count=counts["form"],
        link_count=len(soup.find_all("a", href=True)), script_count=counts["script"],
        iframe_count=counts["iframe"], submit_count=submit_count,
        has_password_input=any(str(tag.get("type", "")).lower() == "password" for tag in inputs),
        has_checkbox=any(str(tag.get("type", "")).lower() == "checkbox" for tag in inputs),
        approval_keywords=tuple(word for word in KEYWORDS if word in text),
    )


def save_html(html: str, url: str, directory: Path) -> Path:
    """Save only on request. Raw HTML may contain tokens; never commit/share as-is."""
    host = urlsplit(url).hostname or "unknown"
    host = re.sub(r"[^a-zA-Z0-9_-]", "_", host)[:100]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    directory.mkdir(parents=True, exist_ok=True)
    for sequence in count():
        suffix = f"_{sequence}" if sequence else ""
        path = directory / f"{timestamp}{suffix}_{host}.html"
        try:
            stream = path.open("x", encoding="utf-8")
        except FileExistsError:
            continue
        with stream:
            stream.write(html)
        return path
