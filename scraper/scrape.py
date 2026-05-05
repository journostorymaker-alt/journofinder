"""
Scraping engine — upgraded multi-strategy version.

Tries multiple strategies for each outlet in order, falling through if one
yields no useful bylines:

  1. RSS feed(s)            — cheap, fast, but many outlets don't expose them
  2. News sitemap           — /sitemap_news.xml or /news-sitemap.xml
  3. Generic sitemap        — /sitemap.xml (parses index, samples articles)
  4. Author directory       — /authors/, /staff/, /meet-the-team/, etc.
  5. Homepage link harvest  — last resort

Politeness:
  - Randomised 2-5 second delay between requests to same domain
  - Honours Crawl-Delay directive in robots.txt
  - Backoff on 429 / 503 errors
  - Browser-style request headers
  - Identifies itself transparently in User-Agent
  - Respects robots.txt
  - Caches successful fetches for 24 hours
  - Hard cap of 100 articles per outlet per scrape run

Resilience:
  - Every outlet wrapped in try/except
  - Status logged to scrape_log
  - Periodic checkpoint commits to database during long runs
"""

import re
import time
import json
import random
import hashlib
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
import feedparser

from db import get_conn, init_db, sync_outlets
from outlets import OUTLETS

USER_AGENT = (
    "JournoFinder/1.0 (+https://github.com/journostorymaker-alt/journofinder; "
    "press research tool; respects robots.txt; contact via repo issues)"
)

# Standard browser-style headers so request fingerprint is consistent
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = timedelta(hours=24)

# Polite scraping params
MIN_DELAY = 2.0
MAX_DELAY = 5.0
MAX_ARTICLES_PER_OUTLET = 100
REQUEST_TIMEOUT = 25
MAX_RETRIES_ON_429 = 2

CHECKPOINT_EVERY_N_OUTLETS = 10

NON_JOURNALIST_BYLINES = {
    "newsdesk", "news desk", "news team", "staff reporter", "staff writer",
    "press association", "pa news agency", "pa reporters", "pa media",
    "reuters", "agency staff", "guest writer", "guest contributor",
    "editor", "editorial team", "the editor", "our reporter",
    "our political editor", "anonymous", "admin", "user", "test",
    "sponsored content", "promoted content", "bbc news", "sky news",
    "itv news", "channel 4 news", "channel 5 news", "wire services",
    "bbc sport", "bbc cymru fyw", "bbc weather", "bbc travel",
    "bbc reporter", "bbc correspondent", "bbc breakfast",
    "letters the editor", "letters editor", "letters to the editor",
    "the team", "our team", "newsroom", "the newsroom",
    "comment", "comments", "leader", "letter writer",
    "press release", "press team", "communications team",
    "guardian staff", "telegraph staff", "times staff",
    "yorkshire post letters", "the yorkshire post letters",
    "the yorkshire post", "yorkshire post staff",
    "the scotsman", "scotsman reporters", "scotsman staff",
    "national world", "national world publishing",
}

SECTION_WORDS = {
    "sport", "news", "comment", "weather", "business", "politics",
    "culture", "lifestyle", "entertainment", "showbiz", "money",
    "travel", "food", "drink", "opinion", "letters", "obituaries",
    "world", "uk", "scotland", "wales", "england", "ireland",
}

_robots_cache = {}
_last_request_time = {}
_domain_failure_streak = {}


# =============================================================================
# Polite HTTP layer
# =============================================================================

def _get_robots(domain):
    """Fetch and cache robots.txt for a domain. Returns (RobotFileParser, crawl_delay)."""
    if domain in _robots_cache:
        return _robots_cache[domain]
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"https://{domain}/robots.txt")
    crawl_delay = None
    try:
        rp.read()
        try:
            cd = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
            if cd:
                crawl_delay = float(cd)
        except Exception:
            pass
    except Exception:
        pass
    _robots_cache[domain] = (rp, crawl_delay)
    return _robots_cache[domain]


def _polite_get(url, accept_xml=False):
    """Rate-limited, robots-aware GET with caching, jitter and backoff."""
    domain = urlparse(url).netloc
    if not domain:
        return None, "invalid_url"
    
    rp, crawl_delay = _get_robots(domain)
    if not rp.can_fetch(USER_AGENT, url):
        return None, "robots_disallow"
    
    cache_key = hashlib.sha256(url.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_key}.html"
    if cache_file.exists():
        age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if age < CACHE_TTL:
            try:
                return cache_file.read_text(encoding="utf-8", errors="replace"), "cache"
            except Exception:
                pass
    
    base_delay = crawl_delay if crawl_delay else random.uniform(MIN_DELAY, MAX_DELAY)
    failures = _domain_failure_streak.get(domain, 0)
    if failures > 0:
        base_delay = min(60.0, base_delay * (1.5 ** failures))
    
    now = time.time()
    if domain in _last_request_time:
        elapsed = now - _last_request_time[domain]
        if elapsed < base_delay:
            time.sleep(base_delay - elapsed)
    _last_request_time[domain] = time.time()
    
    headers = dict(DEFAULT_HEADERS)
    if accept_xml:
        headers["Accept"] = "application/xml,text/xml;q=0.9,*/*;q=0.8"
    
    for attempt in range(MAX_RETRIES_ON_429 + 1):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            
            if r.status_code == 200:
                _domain_failure_streak[domain] = 0
                try:
                    cache_file.write_text(r.text, encoding="utf-8")
                except Exception:
                    pass
                return r.text, "ok"
            
            if r.status_code in (429, 503):
                retry_after = r.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = min(120, int(retry_after))
                    except ValueError:
                        wait = 30
                else:
                    wait = 10 * (2 ** attempt)
                if attempt < MAX_RETRIES_ON_429:
                    time.sleep(wait)
                    continue
                _domain_failure_streak[domain] = failures + 1
                return None, "rate_limited"
            
            _domain_failure_streak[domain] = failures + 1
            return None, f"http_{r.status_code}"
        
        except requests.exceptions.Timeout:
            _domain_failure_streak[domain] = failures + 1
            return None, "timeout"
        except requests.exceptions.RequestException as e:
            _domain_failure_streak[domain] = failures + 1
            return None, f"error:{type(e).__name__}"
    
    return None, "exhausted_retries"


# =============================================================================
# Name parsing & validation
# =============================================================================

def _normalise_name(name):
    name = re.sub(r"[^\w\s]", "", name.lower())
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _looks_like_organisation(name):
    """Detect organisation/section labels (e.g. 'BBC Sport', 'Yorkshire Post')."""
    lower = name.lower().strip()
    org_prefixes = ("bbc ", "itv ", "sky ", "pa ", "reuters ", "channel ",
                    "guardian ", "times ", "sun ", "mirror ",
                    "yorkshire post", "the yorkshire", "national world ",
                    "scotsman ", "the scotsman", "press association ")
    for prefix in org_prefixes:
        if lower.startswith(prefix):
            return True
    parts = lower.split()
    if len(parts) == 1 and parts[0] in SECTION_WORDS:
        return True
    return False


def _looks_like_real_name(name):
    if not name or len(name) < 4 or len(name) > 60:
        return False
    if _normalise_name(name) in NON_JOURNALIST_BYLINES:
        return False
    if _looks_like_organisation(name):
        return False
    parts = name.strip().split()
    if len(parts) < 2:
        return False
    if name.isupper() or name.islower():
        return False
    if not re.match(r"^[A-Za-z][A-Za-z\s'\-\.]+$", name):
        return False
    return True


def _split_name(full_name):
    parts = full_name.strip().split()
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 3:
        if re.match(r"^[A-Z]\.?$", parts[1]):
            return parts[0], parts[2]
        return parts[0], " ".join(parts[1:])
    if len(parts) >= 4:
        return parts[0], " ".join(parts[-2:])
    return parts[0], ""


# =============================================================================
# Specialism extraction
# =============================================================================

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
    blob = (title + " " + url).lower()
    return [tag for tag, keywords in SPECIALISM_KEYWORDS.items()
            if any(k in blob for k in keywords)]


# =============================================================================
# Byline extraction from article HTML
# =============================================================================

def _extract_byline_from_article(html, base_url):
    """Try multiple strategies to find article author(s)."""
    soup = BeautifulSoup(html, "html.parser")
    
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0] if data else {}
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
                        valid = [n for n in names if _looks_like_real_name(n)]
                        if valid:
                            return valid
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    
    for meta_name in ["author", "article:author", "byl", "DC.creator", "twitter:creator"]:
        meta = soup.find("meta", attrs={"name": meta_name}) or soup.find("meta", property=meta_name)
        if meta and meta.get("content"):
            name = meta["content"].strip()
            if not name.startswith("http") and not name.startswith("@") and _looks_like_real_name(name):
                return [name]
    
    byline_selectors = [
        ".byline", ".author", ".article-author", ".by-line", ".author-name",
        '[rel="author"]', ".c-byline", ".story-byline", ".byline__author",
        ".author-link", ".td-post-author-name a", ".meta-author",
        ".article__byline", ".article-meta__author", ".post-author",
        ".entry-author", ".author-info__name", ".m-byline__author-name",
    ]
    for sel in byline_selectors:
        for el in soup.select(sel):
            text = el.get_text(" ", strip=True)
            text = re.sub(r"^by\s+", "", text, flags=re.I)
            text = re.split(r"\s+(?:and|&|\|)\s+", text)[0].strip()
            if _looks_like_real_name(text):
                return [text]
    
    body_text = soup.get_text(" ", strip=True)[:2000]
    m = re.search(r"\bBy\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", body_text)
    if m and _looks_like_real_name(m.group(1)):
        return [m.group(1)]
    
    return []


def _extract_emails_from_page(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    pattern = r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"
    emails = set()
    for m in re.findall(pattern, text):
        if any(bad in m.lower() for bad in ["example.com", "yourdomain", "domain.com", "@2x"]):
            continue
        emails.add(m.lower())
    return emails


# =============================================================================
# Strategy 1: RSS
# =============================================================================

def _strategy_rss(outlet_data, max_articles):
    article_urls = []
    for rss_url in (outlet_data.get("rss") or [])[:3]:
        html, status = _polite_get(rss_url, accept_xml=True)
        if not html:
            continue
        try:
            feed = feedparser.parse(html)
            for entry in feed.entries[:max_articles]:
                if entry.get("link"):
                    article_urls.append({
                        "url": entry["link"],
                        "title": entry.get("title", ""),
                        "date": entry.get("published", ""),
                    })
        except Exception:
            continue
    return article_urls


# =============================================================================
# Strategy 2 & 3: Sitemap
# =============================================================================

def _parse_sitemap_xml(xml_text, base_url):
    """Returns (urls, is_index). urls is list of (url, lastmod) tuples."""
    urls = []
    is_index = False
    try:
        xml_text = xml_text.strip()
        root = ET.fromstring(xml_text)
        ns_strip = lambda t: t.split("}", 1)[-1] if "}" in t else t
        
        if ns_strip(root.tag) == "sitemapindex":
            is_index = True
            for sm in root:
                if ns_strip(sm.tag) == "sitemap":
                    for child in sm:
                        if ns_strip(child.tag) == "loc" and child.text:
                            urls.append((child.text.strip(), None))
                            break
        elif ns_strip(root.tag) == "urlset":
            for u in root:
                if ns_strip(u.tag) != "url":
                    continue
                loc_text = None
                lastmod_text = None
                for child in u:
                    tag = ns_strip(child.tag)
                    if tag == "loc" and child.text:
                        loc_text = child.text.strip()
                    elif tag == "lastmod" and child.text:
                        lastmod_text = child.text.strip()
                if loc_text:
                    urls.append((loc_text, lastmod_text))
    except ET.ParseError:
        pass
    
    return urls, is_index


def _looks_like_article_url(url):
    lower = url.lower()
    skip = ["/tag/", "/topic/", "/category/", "/author/", "/page/",
            "/wp-content/", "/feed/", "/rss/", "/sitemap",
            "/login", "/register", "/subscribe", "/contact",
            "/privacy", "/terms", "/about/", "/help/",
            ".jpg", ".png", ".gif", ".pdf", ".xml"]
    if any(s in lower for s in skip):
        return False
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return False
    if path.count("/") < 1:
        return False
    return True


def _strategy_sitemap(outlet_data, max_articles):
    domain = outlet_data["domain"].split("/")[0]
    candidates = [
        f"https://{domain}/sitemap_news.xml",
        f"https://{domain}/news-sitemap.xml",
        f"https://{domain}/google-news-sitemap.xml",
        f"https://{domain}/sitemap-news.xml",
        f"https://{domain}/sitemap.xml",
        f"https://{domain}/sitemap_index.xml",
    ]
    
    article_urls = []
    
    for sitemap_url in candidates:
        html, status = _polite_get(sitemap_url, accept_xml=True)
        if not html:
            continue
        urls, is_index = _parse_sitemap_xml(html, sitemap_url)
        if not urls:
            continue
        
        if is_index:
            child_urls = [u for u, _ in urls if any(
                kw in u.lower() for kw in ["news", "article", "post", "story"]
            )]
            if not child_urls:
                child_urls = [u for u, _ in urls[:2]]
            else:
                child_urls = child_urls[:2]
            
            for child in child_urls:
                child_html, _ = _polite_get(child, accept_xml=True)
                if not child_html:
                    continue
                child_urls_parsed, _ = _parse_sitemap_xml(child_html, child)
                child_urls_parsed.sort(key=lambda u: u[1] or "", reverse=True)
                for url, lastmod in child_urls_parsed[:max_articles]:
                    if _looks_like_article_url(url):
                        article_urls.append({"url": url, "title": "", "date": lastmod or ""})
                if len(article_urls) >= max_articles:
                    break
        else:
            urls.sort(key=lambda u: u[1] or "", reverse=True)
            for url, lastmod in urls[:max_articles * 2]:
                if _looks_like_article_url(url):
                    article_urls.append({"url": url, "title": "", "date": lastmod or ""})
        
        if article_urls:
            break
    
    return article_urls[:max_articles]


# =============================================================================
# Strategy 4: Author directory walking
# =============================================================================

def _strategy_authors(outlet_data, max_articles):
    """Visit author directory pages, find profile links, harvest their articles."""
    domain = outlet_data["domain"].split("/")[0]
    article_urls = []
    
    candidates = list(outlet_data.get("team_urls") or [])
    common_paths = [
        "/authors/", "/author/", "/staff/", "/our-team/", "/team/",
        "/meet-the-team", "/news/meet-the-team", "/journalists/",
    ]
    for path in common_paths:
        candidates.append(f"https://{domain}{path}")
    
    seen_profile_urls = set()
    
    for dir_url in candidates[:3]:
        html, status = _polite_get(dir_url)
        if not html:
            continue
        
        soup = BeautifulSoup(html, "html.parser")
        profile_links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(dir_url, a["href"])
            href_lower = href.lower()
            if not href.startswith("http"):
                continue
            if domain not in href_lower:
                continue
            if not any(p in href_lower for p in
                       ["/author/", "/authors/", "/staff/", "/profile/",
                        "/meet-the-team/", "/people/", "/journalists/"]):
                continue
            if href in seen_profile_urls:
                continue
            seen_profile_urls.add(href)
            profile_links.append(href)
        
        for profile_url in profile_links[:30]:
            phtml, _ = _polite_get(profile_url)
            if not phtml:
                continue
            psoup = BeautifulSoup(phtml, "html.parser")
            
            for a in psoup.find_all("a", href=True):
                href = urljoin(profile_url, a["href"])
                if domain not in href.lower():
                    continue
                if _looks_like_article_url(href):
                    title = a.get_text(strip=True)[:200]
                    if href not in {x["url"] for x in article_urls}:
                        article_urls.append({"url": href, "title": title, "date": ""})
            
            if len(article_urls) >= max_articles:
                break
        
        if article_urls:
            break
    
    return article_urls[:max_articles]


# =============================================================================
# Strategy 5: Homepage harvest
# =============================================================================

def _strategy_homepage(outlet_data, max_articles):
    domain = outlet_data["domain"].split("/")[0]
    homepage = f"https://{domain}/"
    
    html, status = _polite_get(homepage)
    if not html:
        return []
    
    soup = BeautifulSoup(html, "html.parser")
    article_urls = []
    seen = set()
    
    for a in soup.find_all("a", href=True):
        href = urljoin(homepage, a["href"])
        if domain not in href.lower():
            continue
        if not _looks_like_article_url(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        title = a.get_text(strip=True)[:200]
        article_urls.append({"url": href, "title": title, "date": ""})
        if len(article_urls) >= max_articles:
            break
    
    return article_urls


# =============================================================================
# Per-outlet driver
# =============================================================================

def scrape_outlet(outlet_row):
    """Scrape one outlet by trying strategies in order. Returns (status, byline_count)."""
    outlet_id = outlet_row["id"]
    outlet_data = next((o for o in OUTLETS if o["name"] == outlet_row["name"]), None)
    if not outlet_data:
        return "no_seed_data", 0
    
    article_urls = []
    strategy_used = "none"
    
    article_urls = _strategy_rss(outlet_data, MAX_ARTICLES_PER_OUTLET)
    if article_urls:
        strategy_used = "rss"
    
    if not article_urls:
        article_urls = _strategy_sitemap(outlet_data, MAX_ARTICLES_PER_OUTLET)
        if article_urls:
            strategy_used = "sitemap"
    
    if not article_urls:
        article_urls = _strategy_authors(outlet_data, MAX_ARTICLES_PER_OUTLET)
        if article_urls:
            strategy_used = "authors"
    
    if not article_urls:
        article_urls = _strategy_homepage(outlet_data, MAX_ARTICLES_PER_OUTLET)
        if article_urls:
            strategy_used = "homepage"
    
    seen_urls = set()
    deduped = []
    for a in article_urls:
        if a["url"] and a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            deduped.append(a)
    article_urls = deduped[:MAX_ARTICLES_PER_OUTLET]
    
    bylines_found = 0
    for art in article_urls:
        html, status = _polite_get(art["url"])
        if not html:
            continue
        names = _extract_byline_from_article(html, art["url"])
        if not names:
            continue
        title = art.get("title") or ""
        if not title:
            soup = BeautifulSoup(html[:5000], "html.parser")
            t = soup.find("title")
            if t:
                title = t.get_text(strip=True)[:200]
        keywords = _extract_keywords(title, art["url"])
        for name in names:
            _record_byline(outlet_row, name, {"url": art["url"], "title": title,
                                              "date": art.get("date", "")}, keywords)
            bylines_found += 1
    
    # Newsroom emails — kept SEPARATE from journalists now (was a bug previously)
    for team_url in (outlet_data.get("team_urls") or [])[:1]:
        html, status = _polite_get(team_url)
        if html:
            emails = _extract_emails_from_page(html)
            for email in emails:
                role = _classify_email_role(email)
                if role:
                    _record_newsroom_contact(outlet_id, role, email, team_url)
    
    _log_scrape(outlet_id, "summary", "ok", bylines_found,
                f"strategy: {strategy_used}, articles: {len(article_urls)}, bylines: {bylines_found}")
    
    with get_conn() as conn:
        conn.execute("""
            UPDATE outlets SET last_scraped = CURRENT_TIMESTAMP,
                last_scrape_status = ?, last_scrape_count = ?
            WHERE id = ?
        """, (f"ok:{strategy_used}" if bylines_found else "no_bylines", bylines_found, outlet_id))
    
    return "ok" if bylines_found else "no_bylines", bylines_found


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
    """Insert/update journalist + byline rows. Cross-outlet dedup by name."""
    name = name.strip()
    name_norm = _normalise_name(name)
    first, last = _split_name(name)
    keywords_str = ",".join(keywords) if keywords else ""
    
    with get_conn() as conn:
        existing = conn.execute("""
            SELECT id FROM journalists WHERE name_normalised = ?
        """, (name_norm,)).fetchone()
        
        if existing:
            jid = existing["id"]
            conn.execute("UPDATE journalists SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (jid,))
        else:
            cur = conn.execute("""
                INSERT INTO journalists (full_name, name_normalised, first_name, last_name, primary_outlet_id)
                VALUES (?, ?, ?, ?, ?)
            """, (name, name_norm, first, last, outlet_row["id"]))
            jid = cur.lastrowid
        
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


# =============================================================================
# Main run loop
# =============================================================================

def run_full_scrape(limit=None, region_filter=None):
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
    
    # Shuffle so we don't always hit the same domains in order
    outlets = list(outlets)
    random.shuffle(outlets)
    
    print(f"Scraping {len(outlets)} outlets...")
    print(f"Politeness: {MIN_DELAY}-{MAX_DELAY}s jitter, "
          f"crawl-delay honoured, backoff on 429/503", flush=True)
    
    results = {"ok": 0, "no_bylines": 0, "error": 0, "no_seed_data": 0}
    total_bylines = 0
    
    for i, outlet in enumerate(outlets, 1):
        try:
            print(f"  [{i}/{len(outlets)}] {outlet['name']}...", end=" ", flush=True)
            status, count = scrape_outlet(outlet)
            results[status if status in results else "error"] = results.get(status, 0) + 1
            total_bylines += count
            print(f"{status} ({count} bylines)", flush=True)
        except Exception as e:
            print(f"FAILED: {e}", flush=True)
            results["error"] += 1
            try:
                _log_scrape(outlet["id"], "exception", "error", 0, str(e))
            except Exception:
                pass
        
        if i % CHECKPOINT_EVERY_N_OUTLETS == 0:
            print(f"  --- checkpoint: {i}/{len(outlets)} done, {total_bylines} bylines so far ---",
                  flush=True)
    
    print(f"\nScrape complete: {results}")
    print(f"Total bylines collected this run: {total_bylines}")
    return results


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_full_scrape(limit=limit)
