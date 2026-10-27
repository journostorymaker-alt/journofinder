"""
Profile and patch enrichment.

Works out each journalist's WORKING patch and job title from public,
work-related sources. It runs separately from the main scrape so it never
slows that down.

Steps, cheapest first:

  1. Stories   - where their stories are set. Uses bylines we already hold,
                 so it costs no web requests at all.
  2. Author    - reads one of their recent articles for a link to their
                 author page, then reads that page's bio, job title and
                 links to their professional social profiles.
  3. Bluesky   - searches Bluesky's public profile search by name and keeps
                 the bio only when it clearly matches (same name, and the bio
                 names their outlet).
  4. Web       - OPTIONAL. Only runs if a BRAVE_API_KEY is set. Searches
                 "Name" "Outlet" and reads the result snippets (LinkedIn
                 and Muck Rack headlines show up there). We never fetch
                 LinkedIn, X or Muck Rack pages themselves.

What this deliberately does NOT do:
  - Anything about where a journalist lives. Sentences in bios that talk
    about home, family, being born or growing up somewhere are thrown away
    before any place is read from them.
  - Store whole bios. We keep a short work-focused excerpt (max 280 chars)
    with a link to where it came from.

Hand corrections go in scraper/patch_overrides.txt and always win.

Usage:
  python enrich_profiles.py                   # full run, default time budget
  python enrich_profiles.py --limit 25        # quick test on 25 journalists
  python enrich_profiles.py --stories-only    # step 1 only, no web requests
  python enrich_profiles.py --minutes 120     # stop web steps after 2 hours
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from db import get_conn, init_db  # noqa: E402
from places import PLACE_TO_PATCH, PATCH_REGION, FALSE_FRIENDS  # noqa: E402

# scrape.py gives us the polite, robots-aware, cached fetcher and the
# name normaliser, so enrichment behaves exactly like the main scraper.
import scrape  # noqa: E402

OVERRIDES_FILE = Path(__file__).parent / "patch_overrides.txt"

RECHECK_DAYS = 90            # re-read a journalist's bio every 3 months
ACTIVE_DAYS = 180            # only spend web requests on people active recently
BIO_MAX = 280
# Paid web search limits. Brave's free monthly credit covers about 1,000
# searches. The search step runs at most 10 times a month (Wednesdays and
# Sundays), so 90 a run fits. The monthly cap is the real safety net: once
# 900 searches have been logged this calendar month, no more run until the
# 1st, however many runs or manual tests happen.
MAX_WEB_PER_RUN = 100
MAX_WEB_PER_MONTH = 900
MIN_LOCATED_STORIES = 3      # need at least this many located stories
MIN_LOCATED_NATIONAL = 5     # national reporters need more, as one-off trips are common
STORY_PATCH_SHARE = 0.45     # top area must hold this share of located stories

JOURNO_WORDS = re.compile(
    r"\b(reporter|journalist|correspondent|editor|writer|presenter|producer|"
    r"broadcaster|columnist|critic|news ?desk|newsroom|freelance|sub-?editor|"
    r"commentator|anchor)\b", re.I)

# Sentences with these words are about someone's personal life, not their
# job. We drop them before reading any place names from a bio.
PERSONAL_WORDS = re.compile(
    r"\b(live|lives|living|lived|home|born|grew up|raised|hometown|native|"
    r"originally from|wife|husband|partner|kids|children|son|daughter|mum|"
    r"dad|mother|father|family|dog|cat|married|location|located)\b", re.I)

# Bits of search previews that are about the person's location or the site,
# never about their job. LinkedIn previews show "Location: <town>", which is
# where they live, so it is cut out before anything else is read.
SNIPPET_JUNK = re.compile(
    r"(Location|Lives in|Based in the|Connections?|Followers?|Experience|Education)\s*:[^.|·]*[.|·]?"
    r"|\s*[|·-]\s*LinkedIn\b.*?$|\s*/\s*X\s*$|\s*on X\b|\d[\d,.]*\+?\s*(followers|connections)(\s+on\s+(LinkedIn|X))?",
    re.I | re.M)

# Sentences about past jobs ("previously at the Manchester Evening News")
# say nothing about the current patch.
PAST_WORDS = re.compile(
    r"\b(previously|formerly|former|used to|ex-|before joining|before that|"
    r"spent \d+ years|worked (?:at|for))\b", re.I)

# Region-wide phrases that show up in job titles ("North of England
# correspondent") and map to a top-level region rather than one county.
REGION_PHRASES = [
    (re.compile(r"\bScotland\b|\bScottish\b"), "Scotland"),
    (re.compile(r"\bWales\b|\bWelsh\b"), "Wales"),
    (re.compile(r"\bNorth[- ]East\b"), "North East"),
    (re.compile(r"\bNorth[- ]West\b"), "North West"),
    (re.compile(r"\bYorkshire\b"), "Yorkshire"),
    (re.compile(r"\bWest Midlands\b"), "West Midlands"),
    (re.compile(r"\bEast Midlands\b"), "East Midlands"),
    (re.compile(r"\bMidlands\b"), "Midlands"),
    (re.compile(r"\bEast Anglia\b|\bEast of England\b"), "East of England"),
    (re.compile(r"\bSouth[- ]East\b"), "South East"),
    (re.compile(r"\bSouth[- ]West\b|\bWest Country\b"), "South West"),
    (re.compile(r"\bNorth of England\b|\bNorthern England\b"), "North of England"),
    (re.compile(r"\bLondon\b"), "London"),
]

SOCIAL_HOSTS = {
    "twitter.com": "x", "x.com": "x", "bsky.app": "bluesky",
    "linkedin.com": "linkedin", "muckrack.com": "muckrack",
    "threads.net": "threads", "mastodon.social": "mastodon",
    "journa.host": "mastodon",
}

SPORT_URL = re.compile(
    r"/(sport|sports|football|cricket|rugby[\w-]*|tennis|golf|boxing|racing|"
    r"formula1|f1|motorsport|athletics|cycling|darts|snooker)(/|$)", re.I)

BLUESKY_SEARCH = "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors"
BRAVE_SEARCH = "https://api.search.brave.com/res/v1/web/search"


# =============================================================================
# Schema
# =============================================================================

PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS journalist_profiles (
    -- Keyed by normalised name, not id, so it survives consolidation
    -- merging or removing journalist rows.
    name_normalised TEXT PRIMARY KEY,
    job_title TEXT,
    bio TEXT,                 -- short work-focused excerpt
    bio_source TEXT,          -- 'author_page', 'bluesky', 'web', 'manual'
    bio_url TEXT,             -- where the bio came from (click to check)
    author_url TEXT,
    social_links TEXT,        -- JSON {"x": url, "linkedin": url, ...}
    bio_patch TEXT,           -- patch read from their own bio
    bio_patch_region TEXT,
    story_patch TEXT,         -- patch worked out from where stories are set
    story_patch_region TEXT,
    story_patch_share REAL,   -- share of located stories in that patch
    story_patch_n INTEGER,    -- how many stories could be located
    story_towns TEXT,         -- top towns, comma separated
    patch TEXT,               -- the final answer shown on the dashboard
    patch_region TEXT,
    patch_source TEXT,        -- 'manual', 'bio', 'stories'
    patch_confidence TEXT,    -- 'high', 'medium', 'low'
    author_checked_at TIMESTAMP,
    bluesky_checked_at TIMESTAMP,
    web_checked_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_schema():
    init_db()
    with get_conn() as conn:
        conn.executescript(PROFILE_SCHEMA)


# =============================================================================
# Place matching
# =============================================================================

def _build_place_regex():
    names = sorted(PLACE_TO_PATCH.keys(), key=len, reverse=True)
    pattern = r"(?<![\w'-])(" + "|".join(re.escape(n) for n in names) + r")(?![\w-])"
    return re.compile(pattern)


PLACE_RE = _build_place_regex()
PLACE_SLUGS = {
    n.lower().replace(" ", "-").replace("'", ""): n
    for n in PLACE_TO_PATCH if len(n) >= 5
}
FALSE_FRIEND_RE = re.compile("|".join(re.escape(f) for f in FALSE_FRIENDS))


def places_in_text(text):
    """Return the place names found in a piece of text (case-sensitive)."""
    if not text:
        return []
    text = FALSE_FRIEND_RE.sub(" ", text)
    return PLACE_RE.findall(text)


def places_in_url(url):
    """Place names that appear as a whole path segment, e.g. /sittingbourne/."""
    if not url:
        return []
    found = []
    for seg in urlparse(url).path.lower().split("/"):
        if seg in PLACE_SLUGS:
            found.append(PLACE_SLUGS[seg])
    return found


def work_sentences(text):
    """Split a bio into sentences and drop the personal ones."""
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?|•])\s+|\n+", text)
    keep = [p for p in parts if p.strip() and not PERSONAL_WORDS.search(p)]
    return " ".join(keep).strip()


def patch_from_bio(text):
    """Read a working patch from a bio. Returns (patch, top_region, place) or Nones."""
    work = work_sentences(text)
    work = " ".join(p for p in re.split(r"(?<=[.!?|•])\s+", work) if not PAST_WORDS.search(p))
    if not work:
        return None, None, None
    places = places_in_text(work)
    if places:
        counts = Counter(PLACE_TO_PATCH[p] for p in places)
        patch = counts.most_common(1)[0][0]
        place = next(p for p in places if PLACE_TO_PATCH[p] == patch)
        return patch, PATCH_REGION[patch], place
    for rx, region in REGION_PHRASES:
        if rx.search(work):
            return region, region, region
    return None, None, None


# =============================================================================
# Step 1: patch from where stories are set
# =============================================================================

def story_patches(conn, only_names=None):
    """Work out a patch for every journalist from their byline headlines.
    No web requests. Returns number of journalists given a story patch."""
    rows = conn.execute("""
        SELECT j.name_normalised, b.article_title, b.article_url, o.region AS outlet_region
        FROM bylines b
        JOIN journalists j ON j.id = b.journalist_id
        JOIN outlets o ON o.id = b.outlet_id
    """).fetchall()

    per = defaultdict(list)
    for r in rows:
        if only_names is not None and r["name_normalised"] not in only_names:
            continue
        per[r["name_normalised"]].append(r)

    given = 0
    for name, bylines in per.items():
        area_counts = Counter()
        town_counts = Counter()
        located = 0
        national_outlet = False
        seen_urls = set()
        for b in bylines:
            url = b["article_url"] or ""
            # The same article often turns up under several outlets' feeds
            # (BBC regional feeds carry national stories). Count it once.
            key = url.split("?")[0]
            if key in seen_urls:
                continue
            seen_urls.add(key)
            national = (b["outlet_region"] or "UK") == "UK"
            national_outlet = national_outlet or national
            # National sport desks (and BBC Sport, which appears in BBC
            # regional feeds) travel to fixtures, so their match reports say
            # nothing about a patch. Local paper sport desks are kept.
            if SPORT_URL.search(url) and (national or "bbc.co" in url):
                continue
            places = places_in_text(b["article_title"] or "") + places_in_url(b["article_url"])
            areas = set()
            for p in places:
                area = PLACE_TO_PATCH[p]
                # National outlets mention London constantly; it says
                # nothing about a national reporter's patch.
                if national and area == "London":
                    continue
                areas.add(area)
                town_counts[p] += 1
            if areas:
                located += 1
                for a in areas:
                    area_counts[a] += 1

        patch = region = towns = None
        share = None
        needed = MIN_LOCATED_NATIONAL if national_outlet else MIN_LOCATED_STORIES
        if located >= needed and area_counts:
            top, n = area_counts.most_common(1)[0]
            share = n / located
            if share >= STORY_PATCH_SHARE:
                patch, region = top, PATCH_REGION[top]
                towns = ", ".join(
                    [t for t, _ in town_counts.most_common(8) if PLACE_TO_PATCH[t] == top][:4]
                )
                given += 1
            else:
                # Spread across a wider area: report the top region if one dominates
                region_counts = Counter()
                for a, c in area_counts.items():
                    region_counts[PATCH_REGION[a]] += c
                topr, rn = region_counts.most_common(1)[0]
                if rn / located >= STORY_PATCH_SHARE:
                    patch, region = f"{topr} (wide)", topr
                    towns = ", ".join(t for t, _ in town_counts.most_common(4))
                    share = rn / located
                    given += 1

        conn.execute("""
            INSERT INTO journalist_profiles (name_normalised, story_patch, story_patch_region,
                story_patch_share, story_patch_n, story_towns, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name_normalised) DO UPDATE SET
                story_patch = excluded.story_patch,
                story_patch_region = excluded.story_patch_region,
                story_patch_share = excluded.story_patch_share,
                story_patch_n = excluded.story_patch_n,
                story_towns = excluded.story_towns,
                updated_at = CURRENT_TIMESTAMP
        """, (name, patch, region, round(share, 2) if share else None, located, towns))
    return given


# =============================================================================
# Step 2: author page
# =============================================================================

def _iter_jsonld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                yield item
                for k in ("@graph", "author", "mainEntity"):
                    if k in item:
                        stack.append(item[k])


def _names_match(a, b):
    if not a or not b:
        return False
    return scrape._normalise_name(a) == scrape._normalise_name(b)


def _social_from_links(urls):
    found = {}
    for u in urls:
        if not isinstance(u, str) or not u.startswith("http"):
            continue
        host = urlparse(u).netloc.lower().replace("www.", "")
        for h, kind in SOCIAL_HOSTS.items():
            if host == h or host.endswith("." + h):
                if kind == "linkedin" and "/in/" not in u:
                    continue
                if kind == "x" and any(s in u for s in ("/intent/", "/share", "/status/")):
                    continue
                found.setdefault(kind, u.split("?")[0])
    return found


def find_author_page(article_html, article_url, full_name):
    """From an article, find the author page URL and anything the article's
    own structured data says about the author."""
    soup = BeautifulSoup(article_html, "html.parser")
    info = {"author_url": None, "job_title": None, "description": None, "same_as": []}
    for item in _iter_jsonld(soup):
        if item.get("@type") in ("Person", ["Person"]) and _names_match(item.get("name"), full_name):
            info["author_url"] = info["author_url"] or item.get("url")
            info["job_title"] = info["job_title"] or item.get("jobTitle")
            info["description"] = info["description"] or item.get("description")
            same = item.get("sameAs") or []
            info["same_as"] += same if isinstance(same, list) else [same]
    if not info["author_url"]:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            if ("author" in href or a.get("rel") == ["author"] or "/profile/" in href) \
                    and _names_match(re.sub(r"^by\s+", "", text, flags=re.I), full_name):
                info["author_url"] = href
                break
    if info["author_url"]:
        info["author_url"] = urljoin(article_url, info["author_url"])
        # Only trust author pages on the outlet's own site
        if urlparse(info["author_url"]).netloc.split(":")[0].replace("www.", "") != \
                urlparse(article_url).netloc.split(":")[0].replace("www.", ""):
            info["author_url"] = None
    return info


def read_author_page(html, full_name):
    """Pull bio, job title and social links from an author page."""
    soup = BeautifulSoup(html, "html.parser")
    out = {"bio": None, "job_title": None, "social": {}}
    same_as = []
    for item in _iter_jsonld(soup):
        if item.get("@type") in ("Person", ["Person"]) and _names_match(item.get("name"), full_name):
            out["job_title"] = out["job_title"] or item.get("jobTitle")
            out["bio"] = out["bio"] or item.get("description")
            same = item.get("sameAs") or []
            same_as += same if isinstance(same, list) else [same]
    if not out["bio"]:
        for attrs in ({"name": "description"}, {"property": "og:description"}):
            m = soup.find("meta", attrs=attrs)
            if m and m.get("content") and len(m["content"]) > 40 \
                    and full_name.split()[-1].lower() in m["content"].lower():
                out["bio"] = m["content"]
                break
    if not out["bio"]:
        # First paragraph after the heading that carries their name
        for h in soup.find_all(["h1", "h2"]):
            if _names_match(h.get_text(" ", strip=True), full_name):
                p = h.find_next("p")
                if p:
                    t = p.get_text(" ", strip=True)
                    if 40 <= len(t) <= 800:
                        out["bio"] = t
                break
    links = [a["href"] for a in soup.find_all("a", href=True)]
    out["social"] = _social_from_links(same_as + links)
    # Drop the outlet's own social accounts (linked from every page footer)
    surname = full_name.split()[-1].lower()
    out["social"] = {k: v for k, v in out["social"].items()
                     if k == "linkedin" or surname[:4] in v.lower()}
    return out


def short_bio(text):
    if not text:
        return None
    text = re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text(" ")).strip()
    text = work_sentences(text) or ""
    if len(text) > BIO_MAX:
        text = text[:BIO_MAX].rsplit(" ", 1)[0] + "…"
    return text or None


def job_title_from(text):
    """The first work sentence that names a journalism role, trimmed."""
    work = work_sentences(text or "")
    for sent in re.split(r"(?<=[.!?|•])\s+", work):
        if JOURNO_WORDS.search(sent):
            sent = sent.strip(" .|•")
            return sent[:120]
    return None


def enrich_author(conn, person):
    """Step 2 for one journalist. Returns True if we found a bio."""
    arts = conn.execute("""
        SELECT b.article_url FROM bylines b
        WHERE b.journalist_id = ? AND b.article_url LIKE 'http%'
        ORDER BY b.article_date DESC, b.seen_at DESC LIMIT 2
    """, (person["id"],)).fetchall()
    info = None
    for a in arts:
        html, _ = scrape._polite_get(a["article_url"])
        if not html:
            continue
        info = find_author_page(html, a["article_url"], person["full_name"])
        if info["author_url"] or info["description"] or info["job_title"]:
            break
    bio = job = author_url = None
    social = {}
    if info:
        author_url = info["author_url"]
        bio, job = info["description"], info["job_title"]
        social = _social_from_links(info["same_as"])
        if author_url:
            html, _ = scrape._polite_get(author_url)
            if html:
                page = read_author_page(html, person["full_name"])
                bio = bio or page["bio"]
                job = job or page["job_title"]
                for k, v in page["social"].items():
                    social.setdefault(k, v)
    bio = short_bio(bio)
    job = (job or job_title_from(bio) or None)
    save_bio(conn, person["name_normalised"], bio, job, "author_page",
             author_url, author_url, social, "author_checked_at")
    return bool(bio or job)


# =============================================================================
# Step 3: Bluesky
# =============================================================================

def _outlet_terms(outlet_name, domain):
    terms = set()
    if outlet_name:
        terms.add(outlet_name.lower())
        terms.add(re.sub(r"\s*\(.*?\)", "", outlet_name).lower().replace("the ", "").strip())
    if domain:
        stem = domain.lower().replace("www.", "").split(".")[0]
        if len(stem) > 3:
            terms.add(stem)
    return {t for t in terms if len(t) > 3}


def enrich_bluesky(conn, person):
    import requests
    try:
        r = requests.get(BLUESKY_SEARCH, params={"q": person["full_name"], "limit": 10},
                         headers={"User-Agent": scrape.USER_AGENT}, timeout=20)
        actors = r.json().get("actors", []) if r.status_code == 200 else []
    except Exception:
        actors = []
    terms = _outlet_terms(person["outlet_name"], person["domain"])
    same_name = [a for a in actors if _names_match(a.get("displayName"), person["full_name"])]
    best = None
    for a in same_name:
        desc = (a.get("description") or "").lower()
        if any(t in desc for t in terms):
            best = a
            break
    # We only accept a Bluesky bio that names their outlet. A bio that just
    # says "journalist" is often a side job or a different person.
    bio = job = url = None
    social = {}
    if best:
        url = f"https://bsky.app/profile/{best.get('handle')}"
        bio = short_bio(best.get("description"))
        job = job_title_from(bio)
        social = {"bluesky": url}
    save_bio(conn, person["name_normalised"], bio, job, "bluesky", url, None,
             social, "bluesky_checked_at")
    time.sleep(0.4)
    return bool(bio)


# =============================================================================
# Step 4: optional web search (Brave)
# =============================================================================


# Which kinds of search result are worth reading, best first. Article pages
# are skipped: their previews are about the story, not the journalist.
def read_search_result(res, person):
    """Turn one search result into (rank, bio, job title, url), or None."""
    url = res.get("url", "")
    u = urlparse(url)
    host = u.netloc.lower().replace("www.", "").replace("uk.", "")
    path = u.path.rstrip("/")
    title_raw = BeautifulSoup(res.get("title", ""), "html.parser").get_text(" ")
    desc_raw = BeautifulSoup(res.get("description", ""), "html.parser").get_text(" ")
    if scrape._normalise_name(person["full_name"]) not in scrape._normalise_name(title_raw):
        return None  # the result must be about this person by name
    desc = re.sub(r"\s+", " ", SNIPPET_JUNK.sub(" ", desc_raw)).strip(" .·")
    name_re = re.escape(person["full_name"])

    if host.endswith("linkedin.com") and path.startswith("/in/"):
        # "Jane Smith - Reporter - Eastern Daily Press | LinkedIn"
        t = re.sub(r"\s*[|·-]\s*LinkedIn.*$", "", title_raw, flags=re.I)
        t = re.sub(r"^\s*" + name_re + r"\s*[-–|:,]?\s*", "", t, flags=re.I).strip(" -–|")
        job = t if t and JOURNO_WORDS.search(t) else job_title_from(desc)
        bio = desc if JOURNO_WORDS.search(desc or "") else None
        return (1, short_bio(bio), job, url) if (job or bio) else None

    if host in ("x.com", "twitter.com") and path.count("/") == 1:
        # profile page, not a single post. Preview text is their X bio.
        bio = desc if JOURNO_WORDS.search(desc or "") else None
        return (2, short_bio(bio), job_title_from(bio), url) if bio else (9, None, None, url)

    if host == "bsky.app" and path.startswith("/profile/") and path.count("/") == 2:
        bio = desc if JOURNO_WORDS.search(desc or "") else None
        return (2, short_bio(bio), job_title_from(bio), url) if bio else (9, None, None, url)

    if host == "muckrack.com" and path.count("/") == 1:
        # "Jane Smith's Profile | Eastern Daily Press Journalist | Muck Rack"
        parts = [p.strip() for p in title_raw.split("|")]
        job = None
        if len(parts) >= 3 and JOURNO_WORDS.search(parts[1]):
            job = parts[1]
        bio = re.split(r"As seen in:", desc)[0] if desc else None
        bio = re.sub(r"^.*?Learn more about Muck Rack\W*", "", bio or "").strip(" .") or None
        bio = bio if bio and JOURNO_WORDS.search(bio) else None
        return (3, short_bio(bio), job, url) if (job or bio) else None

    if host.endswith(person["domain"] or "~") and re.search(r"/(author|authors|profile|staff|people)/", path + "/"):
        bio = desc if JOURNO_WORDS.search(desc or "") else None
        return (4, short_bio(bio), job_title_from(bio), url) if bio else None

    return None


def enrich_web(conn, person, api_key):
    import requests
    q = f'"{person["full_name"]}" "{person["outlet_name"]}"'
    try:
        r = requests.get(BRAVE_SEARCH, params={"q": q, "count": 10, "country": "gb"},
                         headers={"X-Subscription-Token": api_key,
                                  "Accept": "application/json"}, timeout=20)
        results = r.json().get("web", {}).get("results", []) if r.status_code == 200 else []
        status = f"http_{r.status_code}"
        note = r.text[:300] if r.status_code != 200 else f"{len(results)} results"
    except Exception as ex:
        results, status, note = [], "error", str(ex)[:300]
    # Keep a record of every paid search so we can see it working (or not)
    conn.execute("INSERT INTO scrape_log (outlet_id, url, status, bylines_found, notes) VALUES (NULL, ?, ?, ?, ?)",
                 (f"brave:{person['full_name']}", status, len(results), note))
    best = None  # (rank, bio, job, url)
    social = {}
    for res in results:
        cand = read_search_result(res, person)
        if not cand:
            continue
        rank, bio_txt, job_txt, link = cand
        social.update(_social_from_links([link]))
        if (bio_txt or job_txt) and (best is None or rank < best[0]):
            best = (rank, bio_txt, job_txt, link)
    bio = job = url = None
    if best:
        _, bio, job, url = best
    save_bio(conn, person["name_normalised"], bio, job, "web", url, None,
             social, "web_checked_at")
    time.sleep(1.1)  # stay under 1 query per second
    return bool(bio)


# =============================================================================
# Saving and final patch decision
# =============================================================================

SOURCE_RANK = {"manual": 0, "author_page": 1, "bluesky": 2, "web": 3}


def save_bio(conn, name_norm, bio, job, source, bio_url, author_url, social, checked_col):
    """Store what we found. A better source never gets overwritten by a
    weaker one (author page beats Bluesky beats web search)."""
    row = conn.execute("SELECT bio_source, social_links FROM journalist_profiles WHERE name_normalised = ?",
                       (name_norm,)).fetchone()
    if not row:
        conn.execute("INSERT INTO journalist_profiles (name_normalised) VALUES (?)", (name_norm,))
        row = {"bio_source": None, "social_links": None}
    merged = json.loads(row["social_links"] or "{}")
    for k, v in (social or {}).items():
        merged.setdefault(k, v)
    conn.execute(f"UPDATE journalist_profiles SET social_links = ?, {checked_col} = CURRENT_TIMESTAMP "
                 "WHERE name_normalised = ?", (json.dumps(merged) if merged else None, name_norm))
    if author_url:
        conn.execute("UPDATE journalist_profiles SET author_url = ? WHERE name_normalised = ?",
                     (author_url, name_norm))
    if not (bio or job):
        return
    current = SOURCE_RANK.get(row["bio_source"], 9)
    if SOURCE_RANK[source] > current:
        return
    p, pr, _ = patch_from_bio(" ".join(x for x in (job, bio) if x))
    conn.execute("""
        UPDATE journalist_profiles SET bio = ?, job_title = ?, bio_source = ?, bio_url = ?,
            bio_patch = ?, bio_patch_region = ?, updated_at = CURRENT_TIMESTAMP
        WHERE name_normalised = ?
    """, (bio, job, source, bio_url, p, pr, name_norm))


SEARCH_FIRST_FILE = Path(__file__).parent / "search_first.txt"


def load_search_first():
    """Names to web-search before anyone else, one per line."""
    if not SEARCH_FIRST_FILE.exists():
        return set()
    names = set()
    for line in SEARCH_FIRST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("|")[0].strip()
        if line and not line.startswith("#"):
            names.add(scrape._normalise_name(line))
    return names


def load_overrides():
    """patch_overrides.txt lines: Full Name | Patch | Job title (optional) | note"""
    out = {}
    if not OVERRIDES_FILE.exists():
        return out
    for line in OVERRIDES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2 or not parts[0]:
            continue
        out[scrape._normalise_name(parts[0])] = {
            "patch": parts[1] or None,
            "job": parts[2] if len(parts) > 2 and parts[2] else None,
        }
    return out


def decide_patches(conn):
    """Pick the final patch for everyone: hand correction > own bio > stories."""
    overrides = load_overrides()
    rows = conn.execute("SELECT * FROM journalist_profiles").fetchall()
    for r in rows:
        patch = region = source = conf = None
        o = overrides.get(r["name_normalised"])
        if o and o["patch"]:
            patch, source, conf = o["patch"], "manual", "high"
            region = PATCH_REGION.get(o["patch"]) or patch_from_bio(o["patch"])[1]
        elif r["bio_patch"]:
            patch, region, source = r["bio_patch"], r["bio_patch_region"], "bio"
            conf = "high"
        elif r["story_patch"]:
            patch, region, source = r["story_patch"], r["story_patch_region"], "stories"
            share = r["story_patch_share"] or 0
            n = r["story_patch_n"] or 0
            conf = "medium" if (share >= 0.65 and n >= 6) else "low"
        job = o["job"] if (o and o["job"]) else r["job_title"]
        conn.execute("""
            UPDATE journalist_profiles SET patch = ?, patch_region = ?, patch_source = ?,
                patch_confidence = ?, job_title = ? WHERE name_normalised = ?
        """, (patch, region, source, conf, job, r["name_normalised"]))
    # Overrides for people with no profile row yet
    for name, o in overrides.items():
        if not conn.execute("SELECT 1 FROM journalist_profiles WHERE name_normalised = ?", (name,)).fetchone():
            conn.execute("""
                INSERT INTO journalist_profiles (name_normalised, patch, patch_region, patch_source,
                    patch_confidence, job_title) VALUES (?, ?, ?, 'manual', 'high', ?)
            """, (name, o["patch"], PATCH_REGION.get(o["patch"] or ""), o["job"]))


# =============================================================================
# Main
# =============================================================================

def queue(conn, check_col, limit, gaps_first=False):
    """Active journalists not checked in the last RECHECK_DAYS, never-checked
    first. Interleaved by outlet so we never hammer one site.

    gaps_first: for the paid web search. Only people whose author page has
    already been tried, and those still with no bio or job title come first,
    so the free searches go where they help most."""
    if gaps_first:
        # 1. Names in search_first.txt (hand-picked, searched straight away)
        picked = []
        wanted = load_search_first()
        if wanted:
            for r in conn.execute(f"""
                SELECT j.id, j.full_name, j.name_normalised, o.name AS outlet_name, o.domain
                FROM journalists j JOIN outlets o ON o.id = j.primary_outlet_id
                LEFT JOIN journalist_profiles p ON p.name_normalised = j.name_normalised
                WHERE p.{check_col} IS NULL OR p.{check_col} < datetime('now', ?)
            """, (f"-{RECHECK_DAYS} days",)).fetchall():
                if r["name_normalised"] in wanted:
                    picked.append(r)
        # 2. Everyone else, least sure first:
        #    no patch > low-confidence patch > medium > high,
        #    and within that people with no bio or job title first,
        #    then the busiest and most recently active.
        rows = conn.execute(f"""
            SELECT j.id, j.full_name, j.name_normalised, o.name AS outlet_name, o.domain
            FROM journalists j
            JOIN outlets o ON o.id = j.primary_outlet_id
            JOIN journalist_profiles p ON p.name_normalised = j.name_normalised
            WHERE COALESCE(j.days_since_last_byline, 0) <= ?
              AND p.author_checked_at IS NOT NULL
              AND (p.{check_col} IS NULL OR p.{check_col} < datetime('now', ?))
            ORDER BY CASE
                       WHEN p.patch IS NULL THEN 0
                       WHEN p.patch_confidence = 'low' THEN 1
                       WHEN p.patch_confidence = 'medium' THEN 2
                       ELSE 3 END,
                     (p.bio IS NOT NULL OR p.job_title IS NOT NULL),
                     p.{check_col} IS NOT NULL,
                     COALESCE(j.days_since_last_byline, 999) <= 30 DESC,
                     j.total_bylines DESC
            LIMIT ?
        """, (ACTIVE_DAYS, f"-{RECHECK_DAYS} days", limit)).fetchall()
        seen = {r["name_normalised"] for r in picked}
        out = picked + [r for r in rows if r["name_normalised"] not in seen]
        return out[:limit]
    rows = conn.execute(f"""
        SELECT j.id, j.full_name, j.name_normalised, o.name AS outlet_name, o.domain
        FROM journalists j
        JOIN outlets o ON o.id = j.primary_outlet_id
        LEFT JOIN journalist_profiles p ON p.name_normalised = j.name_normalised
        WHERE COALESCE(j.days_since_last_byline, 0) <= ?
          AND (p.{check_col} IS NULL OR p.{check_col} < datetime('now', ?))
        ORDER BY p.{check_col} IS NOT NULL, p.{check_col}, j.total_bylines DESC
    """, (ACTIVE_DAYS, f"-{RECHECK_DAYS} days")).fetchall()
    by_outlet = defaultdict(list)
    for r in rows:
        by_outlet[r["outlet_name"]].append(r)
    ordered = []
    while any(by_outlet.values()):
        for k in list(by_outlet):
            if by_outlet[k]:
                ordered.append(by_outlet[k].pop(0))
    return ordered[:limit] if limit else ordered


def run_step(label, check_col, fn, limit, deadline, *extra, gaps_first=False):
    with get_conn() as conn:
        people = queue(conn, check_col, limit, gaps_first=gaps_first)
    print(f"\n{label}: {len(people)} journalists queued", flush=True)
    hits = done = 0
    for person in people:
        if time.time() > deadline:
            print(f"  Time budget reached. Stopping {label} early; the rest go next run.", flush=True)
            break
        try:
            with get_conn() as conn:
                if fn(conn, person, *extra):
                    hits += 1
        except Exception as e:
            print(f"  ! {person['full_name']}: {e}", flush=True)
        done += 1
        if done % 50 == 0:
            print(f"  {label}: {done} checked, {hits} with a bio", flush=True)
    print(f"{label} done: {done} checked, {hits} with a bio", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max journalists per web step (0 = all)")
    ap.add_argument("--minutes", type=float, default=200, help="time budget for web steps")
    ap.add_argument("--stories-only", action="store_true", help="skip all web requests")
    ap.add_argument("--web-queries", type=int, default=0,
                    help="max paid web searches this run (needs BRAVE_API_KEY)")
    args = ap.parse_args()

    ensure_schema()
    start = time.time()

    with get_conn() as conn:
        n = story_patches(conn)
    print(f"Stories: {n} journalists given a patch from where their stories are set", flush=True)

    if not args.stories_only:
        deadline = start + args.minutes * 60
        # Split the time: author pages are the best source, so they get most of it
        author_deadline = start + args.minutes * 60 * 0.75
        run_step("Author pages", "author_checked_at", enrich_author, args.limit, author_deadline)
        # Web search goes before Bluesky so a long Bluesky step can never
        # squeeze it out. It is only a handful of searches.
        key = os.environ.get("BRAVE_API_KEY")
        with get_conn() as conn:
            used = conn.execute("""
                SELECT COUNT(*) FROM scrape_log
                WHERE url LIKE 'brave:%' AND scraped_at >= date('now', 'start of month')
            """).fetchone()[0]
        left = max(0, MAX_WEB_PER_MONTH - used)
        n_web = min(args.web_queries, MAX_WEB_PER_RUN, left)
        print(f"Web searches used this month: {used} of {MAX_WEB_PER_MONTH}. This run: {n_web}", flush=True)
        if key and n_web > 0:
            run_step("Web search", "web_checked_at", enrich_web, n_web,
                     time.time() + 15 * 60, key, gaps_first=True)
        elif n_web > 0:
            print("Web search skipped: no BRAVE_API_KEY set yet", flush=True)
        run_step("Bluesky", "bluesky_checked_at", enrich_bluesky, args.limit, deadline)

    with get_conn() as conn:
        decide_patches(conn)
        stats = conn.execute("""
            SELECT patch_source, patch_confidence, COUNT(*) FROM journalist_profiles
            WHERE patch IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2
        """).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM journalists").fetchone()[0]
        with_job = conn.execute("SELECT COUNT(*) FROM journalist_profiles WHERE job_title IS NOT NULL").fetchone()[0]
    print("\nSummary")
    print(f"  Journalists: {total}")
    for s in stats:
        print(f"  Patch from {s[0]} ({s[1]}): {s[2]}")
    print(f"  With a job title: {with_job}")
    print(f"  Took {round((time.time() - start) / 60, 1)} minutes")


if __name__ == "__main__":
    main()
