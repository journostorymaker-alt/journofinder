"""
Scraping engine.

Strategy: prefer RSS feeds where available — they're cheap, fast, and explicitly
public. For each article in the feed, fetch the page and extract:
  - byline (author name)
  - email if visibly published
  - section/category
  - first ~500 words for keyword extraction

For outlets without RSS, fall back to the homepage and a small number of
section pages.

Politeness:
  - 2 second delay between requests to the same domain
  - Custom user agent identifying us
  - Respect robots.txt for the article paths
  - Cache successful fetches for 24h
  - Hard cap of 30 articles per outlet per scrape run

Resilience:
  - Every outlet wrapped in try/except so one failure doesn't kill the run
  - Status logged to scrape_log table for the dashboard to display
"""

import re
import time
import json
import hashlib
import urllib.robotparser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
import feedparser

from db import get_conn, init_db, sync_outlets
from outlets import OUTLETS

USER_AGENT = (
    "JournoFinder/1.0 (+https://github.com/your-repo/journofinder; "
    "press research tool; respects robots.txt)"
)

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = timedelta(hours=24)

REQUEST_DELAY = 2.0  # seconds between requests to same domain
MAX_ARTICLES_PER_OUTLET = 30
REQUEST_TIMEOUT = 20

# Bylines to ignore — generic newsroom names, not real journalists
NON_JOURNALIST_BYLINES = {
    "newsdesk", "news desk", "news team", "staff reporter", "staff writer",
    "press association", "pa news agency", "pa reporters", "pa media",
    "reuters", "agency staff", "guest writer", "guest contributor",
    "editor", "editorial team", "the editor", "our reporter",
    "our political editor", "anonymous", "admin", "user", "test",
    "sponsored content", "promoted content", "bbc news", "sky news",
    "itv news", "channel 4 news", "wire services",
}

# Robots cache: domain -> RobotFileParser
_robots_cache = {}
_last_request_time = {}  # domain -> timestamp


def _get_robots(domain):
    """Fetch and cache robots.txt for a domain."""
    if domain in _robots_cache:
        return _robots_cache[domain]
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"https://{domain}/robots.txt")
    try:
        rp.read()
    except Exception:
        pass  # if robots.txt unreachable, be permissive but careful
    _robots_cache[domain] = rp
    return rp


def _polite_get(url):
    """Rate-limited, robots-aware GET with caching."""
    domain = urlparse(url).netloc
    
    # Robots check
    rp = _get_robots(domain)
    if not rp.can_fetch(USER_AGENT, url):
        return None, "robots_disallow"
    
    # Cache check
    cache_key = hashlib.sha256(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.html"
    if cache_file.exists():
        age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if age < CACHE_TTL:
            return cache_file.read_text(encoding="utf-8", errors="replace"), "cache"
    
    # Rate limit
    now = time.time()
    if domain in _last_request_time:
        elapsed = now - _last_request_time[domain]
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time[domain] = time.time()
    
    # Fetch
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.9"},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if r.status_code == 200:
            cache_file.write_text(r.text, encoding="utf-8")
            return r.text, "ok"
        return None, f"http_{r.status_code}"
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.RequestException as e:
        return None, f"error:{type(e).__name__}"


def _normalise_name(name):
    """Lowercase, strip punctuation, collapse spaces."""
    name = re.sub(r"[^\w\s]", "", name.lower())
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _looks_like_real_name(name):
    """Filter out 'Newsdesk', 'PA Media', single words, all-caps mastheads, etc."""
    if not name or len(name) < 4 or len(name) > 60:
        return False
    if _normalise_name(name) in NON_JOURNALIST_BYLINES:
        return False
    parts = name.strip().split()
    if len(parts) < 2:
        return False
    # Must look like proper case (people's names)
    if name.isupper() or name.islower():
        return False
    # Must be alphabetic + spaces + apostrophes/hyphens
    if not re.match(r"^[A-Za-z][A-Za-z\s'\-\.]+$", name):
        return False
    return True


def _split_name(full_name):
    """Crude first/last split. Handles Mc/Mac, hyphens, single middle initials."""
    parts = full_name.strip().split()
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 3:
        # If middle is an initial like 'A.' treat as first-last
        if re.match(r"^[A-Z]\.?$", parts[1]):
            return parts[0], parts[2]
        # Otherwise first + last-two-as-surname (e.g. 'Sarah Van Doren')
        return parts[0], " ".join(parts[1:])
    if len(parts) >= 4:
        return parts[0], " ".join(parts[-2:])
    return parts[0], ""


# Topic keywords for specialism extraction.
# These are matched against article titles + URL paths.
SPECIALISM_KEYWORDS = {
    "environment": ["environment", "climate", "pollution", "emissions", "wildlife", "nature", "biodiversity", "ecology", "rewilding", "river", "sewage", "carbon"],
    "agriculture": ["farming", "agriculture", "farmer", "crop", "livestock", "dairy", "defra", "cap", "subsidy", "rural"],
    "fisheries": ["fishing", "fishery", "salmon", "aquaculture", "fish farm", "trawler"],
    "energy": ["energy", "electricity", "gas", "oil", "renewable", "solar", "wind", "nuclear", "ofgem", "octopus"],
    "politics": ["politics", "westminster", "parliament", "mp ", "minister", "government", "downing street", "cabinet"],
    "business": ["business", "economy", "company", "shares", "ftse", "earnings", "profit"],
    "crime": ["crime", "police", "court", "trial", "arrest", "murder", "fraud"],
    "health": ["health", "nhs", "hospital", "doctor", "patient", "medical"],
    "education": ["school", "education", "teacher", "pupil", "ofsted", "university"],
    "transport": ["transport", "rail", "road", "train", "bus", "motorway"],
    "housing": ["housing", "homeless", "rent", "landlord", "council house", "planning"],
    "investigation": ["investigation", "exclusive", "revealed", "uncovered", "exposed", "foi"],
    "sport": ["football", "cricket", "rugby", "premier league", "match", "goal"],
    "culture": ["arts", "music", "theatre", "film", "review", "festival"],
    "local_government": ["council", "councillor", "mayor", "local authority"],
}


def _extract_keywords(title, url):
    """Return list of specialism tags matching title or URL path."""
    blob = (title + " " + url).lower()
    found = []
    for tag, keywords in SPECIALISM_KEYWORDS.items():
        if any(k in blob for k in keywords):
            found.append(tag)
    return found


# ---------- Byline extractors ----------
# Different CMS platforms expose bylines differently. We try in order.

def _extract_byline_from_article(html, base_url):
    """Try multiple strategies to find the article's author."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Strategy 1: JSON-LD structured data — most reliable
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0] if data else {}
            # NewsArticle / Article schemas
            authors = data.get("author")
            if authors:
                if isinstance(authors, dict):
                    authors = [authors]
                if isinstance(authors, list):
                    names = []
                    for a in authors:
                        if isinstance(a, dict) and a.get("name"):
                            names.append(a["name"])
                        elif isinstance(a, str):
                            names.append(a)
                    if names:
                        return [n for n in names if _looks_like_real_name(n)]
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    
    # Strategy 2: meta tags
    for meta_name in ["author", "article:author", "byl", "DC.creator"]:
        meta = soup.find("meta", attrs={"name": meta_name}) or soup.find("meta", property=meta_name)
        if meta and meta.get("content"):
            name = meta["content"].strip()
            # Sometimes this is a URL — skip those
            if not name.startswith("http") and _looks_like_real_name(name):
                return [name]
    
    # Strategy 3: common byline class names
    byline_selectors = [
        ".byline", ".author", ".article-author", ".by-line", ".author-name",
        '[rel="author"]', ".c-byline", ".story-byline", ".byline__author",
        ".author-link", ".td-post-author-name a", ".meta-author",
    ]
    for sel in byline_selectors:
        for el in soup.select(sel):
            text = el.get_text(" ", strip=True)
            # Strip leading "By "
            text = re.sub(r"^by\s+", "", text, flags=re.I)
            # Take first name before " and ", " & ", " | "
            text = re.split(r"\s+(?:and|&|\|)\s+", text)[0].strip()
            if _looks_like_real_name(text):
                return [text]
    
    # Strategy 4: text pattern "By Firstname Lastname"
    body_text = soup.get_text(" ", strip=True)[:2000]
    m = re.search(r"\bBy\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", body_text)
    if m and _looks_like_real_name(m.group(1)):
        return [m.group(1)]
    
    return []


def _extract_emails_from_page(html):
    """Find any visible email addresses on a page (for masthead/team pages)."""
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    pattern = r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"
    emails = set()
    for m in re.findall(pattern, text):
        # Filter out obvious junk
        if any(bad in m.lower() for bad in ["example.com", "yourdomain", "domain.com", "@2x"]):
            continue
        emails.add(m.lower())
    return emails


# ---------- Main scraper for one outlet ----------

def scrape_outlet(outlet_row):
    """Scrape one outlet. Returns (status, byline_count)."""
    outlet_id = outlet_row["id"]
    outlet_data = next((o for o in OUTLETS if o["name"] == outlet_row["name"]), None)
    if not outlet_data:
        return "no_seed_data", 0
    
    rss_urls = outlet_data.get("rss", []) or []
    team_urls = outlet_data.get("team_urls", []) or []
    
    article_urls = []
    
    # Collect article URLs from RSS
    for rss_url in rss_urls[:2]:  # max 2 feeds per outlet
        html, status = _polite_get(rss_url)
        if html:
            try:
                feed = feedparser.parse(html)
                for entry in feed.entries[:MAX_ARTICLES_PER_OUTLET]:
                    article_urls.append({
                        "url": entry.get("link"),
                        "title": entry.get("title", ""),
                        "date": entry.get("published", ""),
                    })
            except Exception as e:
                _log_scrape(outlet_id, rss_url, "parse_error", 0, str(e))
    
    # Dedupe article URLs
    seen_urls = set()
    article_urls = [a for a in article_urls if a["url"] and not (a["url"] in seen_urls or seen_urls.add(a["url"]))]
    article_urls = article_urls[:MAX_ARTICLES_PER_OUTLET]
    
    # Scrape each article for bylines
    bylines_found = 0
    for art in article_urls:
        html, status = _polite_get(art["url"])
        if not html:
            continue
        names = _extract_byline_from_article(html, art["url"])
        if not names:
            continue
        keywords = _extract_keywords(art["title"], art["url"])
        for name in names:
            _record_byline(outlet_row, name, art, keywords)
            bylines_found += 1
    
    # Scrape team/masthead pages for verified emails
    for team_url in team_urls[:1]:  # one per outlet
        html, status = _polite_get(team_url)
        if html:
            emails = _extract_emails_from_page(html)
            if emails:
                _log_scrape(outlet_id, team_url, "ok", len(emails), f"masthead emails: {len(emails)}")
                # We don't auto-link these to journalists — that requires
                # name-near-email proximity matching, which we'll do in
                # consolidation. For now, just store newsroom-level finds.
                for email in emails:
                    role = _classify_email_role(email)
                    if role:
                        _record_newsroom_contact(outlet_id, role, email, team_url)
    
    _log_scrape(outlet_id, "summary", "ok", bylines_found,
                f"articles: {len(article_urls)}, bylines: {bylines_found}")
    
    with get_conn() as conn:
        conn.execute("""
            UPDATE outlets SET last_scraped = CURRENT_TIMESTAMP,
                last_scrape_status = ?, last_scrape_count = ?
            WHERE id = ?
        """, ("ok" if bylines_found else "no_bylines", bylines_found, outlet_id))
    
    return "ok", bylines_found


def _classify_email_role(email):
    local = email.split("@")[0].lower()
    role_map = {
        "newsdesk": "newsdesk", "news": "newsdesk", "tips": "tips",
        "editor": "editor", "editorial": "editor", "planning": "planning",
        "diary": "planning", "environment": "environment_desk",
        "business": "business_desk", "politics": "politics_desk",
        "letters": "letters", "press": "press", "info": None, "hello": None,
        "contact": None, "admin": None,
    }
    for key, role in role_map.items():
        if key in local:
            return role
    return None


def _record_byline(outlet_row, name, article, keywords):
    """Insert/update journalist + byline rows."""
    name = name.strip()
    name_norm = _normalise_name(name)
    first, last = _split_name(name)
    keywords_str = ",".join(keywords) if keywords else ""
    
    with get_conn() as conn:
        # Find or create journalist (matching on normalised name + outlet)
        existing = conn.execute("""
            SELECT id FROM journalists WHERE name_normalised = ? AND primary_outlet_id = ?
        """, (name_norm, outlet_row["id"])).fetchone()
        
        if existing:
            jid = existing["id"]
            conn.execute("UPDATE journalists SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (jid,))
        else:
            cur = conn.execute("""
                INSERT INTO journalists (full_name, name_normalised, first_name, last_name, primary_outlet_id)
                VALUES (?, ?, ?, ?, ?)
            """, (name, name_norm, first, last, outlet_row["id"]))
            jid = cur.lastrowid
        
        # Insert byline (ignore duplicates)
        conn.execute("""
            INSERT OR IGNORE INTO bylines (journalist_id, outlet_id, article_url, article_title, article_date, keywords)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (jid, outlet_row["id"], article["url"], article["title"], article.get("date", ""), keywords_str))


def _record_newsroom_contact(outlet_id, role, email, source):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO newsroom_contacts (outlet_id, role, email, confidence, source)
            VALUES (?, ?, ?, ?, ?)
        """, (outlet_id, role, email, "verified", source))


def _log_scrape(outlet_id, url, status, count, notes):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO scrape_log (outlet_id, url, status, bylines_found, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (outlet_id, url, status, count, notes))


def run_full_scrape(limit=None, region_filter=None):
    """Scrape all outlets. Use limit=N for testing."""
    init_db()
    sync_outlets(OUTLETS)
    
    with get_conn() as conn:
        query = "SELECT * FROM outlets"
        params = []
        if region_filter:
            query += " WHERE region LIKE ?"
            params.append(f"%{region_filter}%")
        outlets = conn.execute(query, params).fetchall()
    
    if limit:
        outlets = outlets[:limit]
    
    print(f"Scraping {len(outlets)} outlets...")
    results = {"ok": 0, "no_bylines": 0, "error": 0}
    total_bylines = 0
    
    for i, outlet in enumerate(outlets, 1):
        try:
            print(f"  [{i}/{len(outlets)}] {outlet['name']}...", end=" ", flush=True)
            status, count = scrape_outlet(outlet)
            results[status if status in results else "error"] = results.get(status, 0) + 1
            total_bylines += count
            print(f"{status} ({count} bylines)")
        except Exception as e:
            print(f"FAILED: {e}")
            results["error"] += 1
            _log_scrape(outlet["id"], "exception", "error", 0, str(e))
    
    print(f"\nScrape complete: {results}")
    print(f"Total bylines collected this run: {total_bylines}")
    return results


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_full_scrape(limit=limit)
