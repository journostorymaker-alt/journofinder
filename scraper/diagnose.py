"""
Diagnose outlets that have stopped returning bylines.

Fetches each outlet's feed and a couple of article pages exactly as the
scraper does, and writes a plain report of what came back: HTTP status,
page size, and every place a byline might be hiding (structured data,
meta tags, byline-looking HTML). No database changes.

Usage:
  python diagnose.py "Daily Mail" "Metro" ...      # named outlets
  python diagnose.py                               # every outlet with 0 bylines last run
"""

import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
import scrape  # noqa: E402
from outlets import OUTLETS  # noqa: E402
from db import get_conn  # noqa: E402

REPORT = Path(__file__).parent.parent / "diagnostics.txt"


def get(url):
    try:
        r = requests.get(url, headers=scrape.DEFAULT_HEADERS, timeout=25, allow_redirects=True)
        return r.status_code, r.text, r.url
    except Exception as e:
        return f"error {type(e).__name__}", "", url


def byline_clues(html):
    soup = BeautifulSoup(html, "html.parser")
    clues = []
    for s in soup.find_all("script", type="application/ld+json"):
        txt = (s.string or "")[:4000]
        for m in re.finditer(r'"author"\s*:\s*(\[[^\]]{0,400}\]|\{[^}]{0,400}\}|"[^"]{0,100}")', txt):
            clues.append("ld+json author: " + m.group(1)[:300])
    for m in soup.find_all("meta"):
        k = (m.get("name") or m.get("property") or "").lower()
        if "author" in k or k in ("byl", "dc.creator", "parsely-author", "sailthru.author"):
            clues.append(f"meta {k}: {m.get('content', '')[:150]}")
    for el in soup.select('[class*="author"], [class*="byline"], [rel="author"], [data-testid*="author"], [itemprop="author"]')[:8]:
        clues.append(f"html <{el.name} class={' '.join(el.get('class') or [])[:60]}>: "
                     f"{el.get_text(' ', strip=True)[:120]}")
    m = re.search(r'"(?:authorName|author_name|byline)"\s*:\s*"([^"]{2,80})"', html)
    if m:
        clues.append("inline json: " + m.group(1))
    return clues or ["(no byline clues found)"]


def article_links_from_feed(text):
    links = re.findall(r"<link>\s*(https?://[^<\s]+)\s*</link>", text)
    links += re.findall(r'<link[^>]+href="(https?://[^"]+)"', text)
    links += re.findall(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", text)
    return [l for l in links if l.count("/") > 3]


def diagnose(outlet, out):
    out.append("=" * 70)
    out.append(f"{outlet['name']}  ({outlet['domain']})")
    rp, _ = scrape._get_robots(outlet["domain"].split("/")[0])
    feeds = list(outlet.get("rss") or [])
    base = "https://" + outlet["domain"].split("/")[0]
    feeds += [base + p for p in ("/sitemap_news.xml", "/news-sitemap.xml", "/sitemap.xml")]
    arts = []
    for f in feeds[:4]:
        status, text, final = get(f)
        n = len(article_links_from_feed(text)) if isinstance(status, int) else 0
        out.append(f"  feed {f} -> {status}, {len(text)} bytes, {n} links"
                   + (f", redirected to {final}" if final != f else ""))
        if status == 200 and n and not arts:
            arts = article_links_from_feed(text)[:12]
    if not arts:
        status, text, _ = get(base + "/")
        out.append(f"  homepage -> {status}, {len(text)} bytes")
        arts = [l for l in re.findall(r'href="(https?://[^"]+|/[^"]+)"', text)
                if re.search(r"/(news|article|politics|uk)[/-]", l)][:12]
        arts = [l if l.startswith("http") else base + l for l in arts]
    shown = 0
    for a in arts:
        if shown >= 2:
            break
        allowed = rp.can_fetch(scrape.USER_AGENT, a)
        status, html, final = get(a)
        out.append(f"  article {a}\n    robots allows: {allowed}; -> {status}, {len(html)} bytes")
        if status == 200:
            names = scrape._extract_byline_from_article(html, a)
            out.append(f"    scraper's byline reader finds: {names}")
            for c in byline_clues(html)[:10]:
                out.append(f"    {c}")
            shown += 1


def main():
    names = sys.argv[1:]
    if not names:
        with get_conn() as conn:
            names = [r["name"] for r in conn.execute(
                "SELECT name FROM outlets WHERE last_scrape_count = 0 AND tier IN ('national','broadcast')")]
    out = []
    for n in names:
        o = next((x for x in OUTLETS if x["name"] == n), None)
        if not o:
            out.append(f"{n}: not in outlets.py")
            continue
        try:
            diagnose(o, out)
        except Exception as e:
            out.append(f"  FAILED: {e}")
    REPORT.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
