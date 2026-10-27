"""
Find journalists at outlets the scraper can't read (broadcasters with no
written bylines, paywalled papers, trade titles that block scrapers).

Uses the Brave web search API and reads only the result previews of
LinkedIn and Muck Rack profile pages. It never opens those pages.

Someone is only added when the preview shows ALL of:
  - a real-looking name at the start of the title
  - the outlet name in their CURRENT job line (not "former", not "ex-")
  - a journalism job (reporter, correspondent, editor, presenter...)

New people get their job title and a link to the profile, so you can check
them in one click. They have no bylines, so their email is a pattern guess
from the outlet, as with everyone else.

Every search counts towards the shared 30-day limit in enrich_profiles.py,
so this can never take the account out of Brave's free credit.

Usage:
  python discover.py --max-searches 150
  python discover.py --max-searches 10 --outlets "Farmers Weekly,ENDS Report"
  python discover.py --dry-run          # show the searches, spend nothing
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
import scrape  # noqa: E402
from db import get_conn  # noqa: E402
import enrich_profiles as ep  # noqa: E402

BRAVE_SEARCH = "https://api.search.brave.com/res/v1/web/search"

JOB_WORDS = re.compile(
    r"\b(reporter|journalist|correspondent|editor|presenter|producer|"
    r"broadcaster|columnist|writer|anchor|newsreader|news ?desk|"
    r"video ?journalist|camera ?operator|planning|bureau chief)\b", re.I)
# Staff of overseas editions or sister papers abroad (Farmers Weekly NZ,
# Daily Mail US, Sky News Australia...). Not useful for UK pitching.
OVERSEAS = re.compile(
    r"\b(NZ|New Zealand|Australia|Australian|US|U\.S\.|USA|America|American|Canada|"
    r"India|Asia|Ireland|Irish|Africa|Dubai|Middle East|Hong Kong|Singapore|Sydney|"
    r"Melbourne|New York|Washington|Los Angeles|Feilding)\b")
FORMER = re.compile(r"\b(former|formerly|ex-|previously|retired|alumni|alumnus)\b", re.I)

# outlet name in the database -> (phrases that must appear in the job line,
#                                  extra search pages to fetch: 0 = one page)
TARGETS = {
    # Broadcasters
    "ITV News (National)": (["ITV News", "ITN"], 1),
    "ITV News London": (["ITV News London", "ITV London"], 0),
    "ITV News Granada": (["ITV Granada", "Granada Reports", "ITV News Granada"], 0),
    "ITV News Tyne Tees": (["ITV Tyne Tees", "ITV News Tyne Tees"], 0),
    "ITV News Calendar": (["ITV Calendar", "ITV News Calendar", "ITV Yorkshire"], 0),
    "ITV News Anglia": (["ITV Anglia", "ITV News Anglia"], 0),
    "ITV News Central": (["ITV Central", "ITV News Central"], 0),
    "ITV News Meridian": (["ITV Meridian", "ITV News Meridian"], 0),
    "ITV News West Country": (["ITV West Country", "ITV News West Country"], 0),
    "ITV News Border": (["ITV Border", "ITV News Border"], 0),
    "ITV Wales": (["ITV Wales", "ITV Cymru"], 0),
    "Sky News": (["Sky News"], 1),
    "Channel 4 News": (["Channel 4 News"], 0),
    "Channel 5 News": (["Channel 5 News", "5 News"], 0),
    "LBC": (["LBC"], 0),
    # Paywalled or blocked papers
    "The Times": (["The Times", "Times Newspapers", "News UK"], 1),
    "The Sunday Times": (["The Sunday Times", "Sunday Times"], 0),
    "Financial Times": (["Financial Times"], 1),
    "The Sun": (["The Sun"], 0),
    "Daily Mail": (["Daily Mail", "MailOnline", "Mail on Sunday"], 1),
    "Reuters UK": (["Reuters"], 0),   # searches add "London", see EXTRA_TERMS
    # Trade and specialist titles that matter for GBF
    "Farmers Weekly": (["Farmers Weekly"], 0),
    "ENDS Report": (["ENDS Report", "ENDS"], 0),
}

# The outlet's X handle, as journalists write it in their bios. Outlets
# listed here also get an X search.
X_HANDLES = {
    "ITV News (National)": "@itvnews",
    "Sky News": "@SkyNews",
    "Channel 4 News": "@Channel4News",
    "Channel 5 News": "@5_News",
    "LBC": "@LBC",
    "The Times": "@thetimes",
    "The Sunday Times": "@thesundaytimes",
    "Financial Times": "@FT",
    "The Sun": "@TheSun",
    "Daily Mail": "@DailyMailUK",
    "Farmers Weekly": "@FarmersWeekly",
    "ENDS Report": "@ENDSreport",
}

# Extra words added to the search for global outlets, so we only find
# their UK-based staff
EXTRA_TERMS = {
    "Reuters UK": '"London"',
}

# Phrases that look like an outlet match but aren't
NOT_THIS_OUTLET = {
    "The Sun": re.compile(r"Sun(day)? (Post|Herald|Mail|Express|Mirror|Times)|Morning Star", re.I),
    "The Times": re.compile(r"(Sunday|Financial|Glasgow|Hereford|Wiltshire|Irish|New York|Los Angeles|Byline|Shetland|Eastern Daily|Daily) Times|Times Higher|Times Educational|TES\b|Times Radio", re.I),
    "Daily Mail": re.compile(r"Hull Daily Mail|Daily Mail (and|&) General Trust|Mail Metro Media", re.I),
    "ITV News (National)": re.compile(r"ITV (News )?(London|Granada|Tyne Tees|Calendar|Anglia|Central|Meridian|West Country|Border|Wales|Cymru)|ITV Studios|ITV Sport|ITVX", re.I),
}

NAME_RE = re.compile(r"^([A-Z][a-zA-Z'’-]+(?:\s+[A-Z][a-zA-Z'’-]+){1,3})\b")


def search(api_key, q, offset=0):
    r = requests.get(BRAVE_SEARCH, params={"q": q, "count": 20, "offset": offset, "country": "gb"},
                     headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                     timeout=25)
    results = r.json().get("web", {}).get("results", []) if r.status_code == 200 else []
    note = f"{len(results)} results" if r.status_code == 200 else r.text[:300]
    with get_conn() as conn:
        conn.execute("INSERT INTO scrape_log (outlet_id, url, status, bylines_found, notes) "
                     "VALUES (NULL, ?, ?, ?, ?)",
                     (f"brave-discover:{q}#p{offset}"[:300], f"http_{r.status_code}", len(results), note))
    time.sleep(1.1)
    return results


def queries_for(outlet, phrases):
    main = phrases[0]
    extra = (" " + EXTRA_TERMS[outlet]) if outlet in EXTRA_TERMS else ""
    roles = "(reporter OR correspondent OR editor OR presenter OR journalist OR producer)"
    qs = [
        f'site:linkedin.com/in "{main}" {roles}{extra}',
        f'site:muckrack.com "{main}"{extra}',
    ]
    if outlet in X_HANDLES:
        # On-air correspondents often have no LinkedIn or Muck Rack profile,
        # but nearly all have an X bio like "Health Editor @itvnews".
        qs.append(f'site:x.com "{X_HANDLES[outlet]}" (correspondent OR editor OR presenter OR reporter){extra}')
    return qs


def parse_result(res, outlet, phrases):
    """Return (full_name, job_title, url) if this result is a current
    journalist at the outlet, else None."""
    url = res.get("url", "")
    u = urlparse(url)
    host = u.netloc.lower().replace("www.", "").replace("uk.", "")
    title = BeautifulSoup(res.get("title", ""), "html.parser").get_text(" ").strip()
    desc = BeautifulSoup(res.get("description", ""), "html.parser").get_text(" ").strip()

    if host.endswith("linkedin.com") and u.path.startswith("/in/"):
        # "Jane Smith - Political Correspondent - ITV News | LinkedIn"
        t = re.sub(r"\s*[|·]\s*LinkedIn.*$", "", title, flags=re.I)
        parts = [p.strip() for p in re.split(r"\s+[-–]\s+", t) if p.strip()]
        if len(parts) < 2:
            return None
        name, job_line = parts[0], " - ".join(parts[1:])
    elif host == "muckrack.com" and u.path.count("/") == 1 and len(u.path) > 2:
        # "Jane Smith's Profile | ITV News Journalist | Muck Rack"
        parts = [p.strip() for p in title.split("|")]
        if len(parts) < 3:
            return None
        name = re.sub(r"[’']s Profile$", "", parts[0]).strip()
        job_line = parts[1]
        # Muck Rack lists several outlets; only trust the first one
        first_outlet = re.split(r",| and ", job_line)[0]
        if not any(p.lower() in first_outlet.lower() for p in phrases):
            return None
    elif host in ("x.com", "twitter.com") and u.path.count("/") == 1 and len(u.path) > 2:
        # Title: "Jane Smith (@janesmith) / X"   Preview: their bio
        name = re.sub(r"\s*\(@?\w+\).*$", "", title).strip()
        name = re.sub(r"\s*(/|on)\s*X\s*$", "", name).strip()
        bio = re.sub(r"\s+", " ", desc)
        handle = X_HANDLES.get(outlet, "").lower()
        # The bio must name the outlet (by handle or name) next to a job
        if not (handle and handle in bio.lower()) and not any(p.lower() in bio.lower() for p in phrases):
            return None
        # Job line is the bio sentence that names the outlet
        job_line = next((sent for sent in re.split(r"(?<=[.!?|•·])\s+|\s+[|•·]\s+", bio)
                         if (handle and handle in sent.lower()) or any(p.lower() in sent.lower() for p in phrases)), "")
        if handle and handle in job_line.lower():
            # "@itvnews" counts as the outlet name for the checks below
            job_line = re.sub(re.escape(handle), phrases[0], job_line, flags=re.I)
        job_line = job_line[:120]
    else:
        return None

    m = NAME_RE.match(name)
    if not m or not scrape._looks_like_real_name(m.group(1)):
        return None
    name = m.group(1)
    if not any(p.lower() in job_line.lower() for p in phrases):
        return None
    if outlet in NOT_THIS_OUTLET and NOT_THIS_OUTLET[outlet].search(job_line):
        return None
    if FORMER.search(job_line) or FORMER.search(desc[:80]):
        return None
    if outlet in EXTRA_TERMS:
        # Global outlet: the preview must also show they're UK-based
        if not re.search(r"\b(London|UK|United Kingdom|Britain|British)\b", job_line + " " + desc):
            return None
    if OVERSEAS.search(job_line):
        return None
    if not JOB_WORDS.search(job_line):
        # "Joe Bloggs – Sky News | LinkedIn" with "Producer at Sky News" in the preview
        first = re.split(r"(?<=[.!?·])\s", desc)[0][:120]
        if JOB_WORDS.search(first) and any(p.lower() in first.lower() for p in phrases) \
                and not FORMER.search(first):
            job_line = first
        else:
            return None
    job = ep.SNIPPET_JUNK.sub(" ", job_line).strip(" -–|")
    return name, job[:120], url


def add_journalist(conn, outlet_row, name, job, url):
    """Add a newly found journalist. Never moves someone we already hold."""
    norm = scrape._normalise_name(name)
    if norm in ep_excluded():
        return "excluded"
    existing = conn.execute("SELECT id FROM journalists WHERE name_normalised = ?", (norm,)).fetchone()
    if existing:
        status = "known"
    else:
        first, last = scrape._split_name(name)
        conn.execute("""
            INSERT INTO journalists (full_name, name_normalised, first_name, last_name,
                primary_outlet_id, classification, total_bylines, primary_region, primary_tier)
            VALUES (?, ?, ?, ?, ?, 'unclear', 0, ?, ?)
        """, (name, norm, first, last, outlet_row["id"], outlet_row["region"], outlet_row["tier"]))
        status = "added"
    # Store the job title and source link as a profile (web search source)
    social = ep._social_from_links([url])
    social.setdefault("linkedin" if "linkedin" in url else "muckrack", url)
    ep.save_bio(conn, norm, None, job, "web", url, None, social, "web_checked_at")
    return status


_excluded = None


def ep_excluded():
    global _excluded
    if _excluded is None:
        f = Path(__file__).parent / "excluded_names.txt"
        _excluded = set()
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.split("#")[0].strip()
                if line:
                    _excluded.add(scrape._normalise_name(line))
    return _excluded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-searches", type=int, default=0)
    ap.add_argument("--outlets", default="", help="comma-separated outlet names (default: all targets)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ep.ensure_schema()
    wanted = [o.strip() for o in args.outlets.split(",") if o.strip()] or list(TARGETS)
    plan = []
    for outlet in wanted:
        if outlet not in TARGETS:
            print(f"Skipping {outlet}: not in the target list")
            continue
        phrases, extra_pages = TARGETS[outlet]
        for q in queries_for(outlet, phrases):
            for page in range(extra_pages + 1):
                plan.append((outlet, q, page))

    with get_conn() as conn:
        left, used = ep.brave_searches_left(conn)
    budget = min(args.max_searches, left, len(plan))
    print(f"Searches planned: {len(plan)}. Used in the last 30 days: {used} of "
          f"{ep.MAX_WEB_PER_MONTH}. Allowed this run: {budget}")
    if args.dry_run:
        for p in plan:
            print("  ", p)
        return
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        print("No BRAVE_API_KEY set. Nothing searched.")
        return

    # Never repeat a search run in the last 60 days: it would just return
    # the same people and waste free searches.
    with get_conn() as conn:
        done = {r[0] for r in conn.execute(
            "SELECT url FROM scrape_log WHERE url LIKE 'brave-discover:%' "
            "AND scraped_at >= datetime('now', '-60 days')")}
    def already(q, page):
        key = f"brave-discover:{q}"[:300]
        return f"{key}#p{page}"[:300] in done or key in done
    skipped = [p for p in plan if already(p[1], p[2])]
    plan = [p for p in plan if not already(p[1], p[2])]
    if skipped:
        print(f"Skipping {len(skipped)} searches already run in the last 60 days")
    # Spread the budget so every outlet gets its first page before any
    # outlet gets a second page.
    plan.sort(key=lambda p: p[2])
    budget = min(budget, len(plan))
    print(f"Running {budget} new searches")
    totals = {}
    for outlet, q, page in plan[:budget]:
        results = search(key, q, offset=page)
        with get_conn() as conn:
            orow = conn.execute("SELECT id, region, tier FROM outlets WHERE name = ?", (outlet,)).fetchone()
            if not orow:
                print(f"  {outlet}: not in database")
                continue
            for res in results:
                hit = parse_result(res, outlet, TARGETS[outlet][0])
                if not hit:
                    continue
                status = add_journalist(conn, orow, *hit)
                totals.setdefault(outlet, {"added": 0, "known": 0, "excluded": 0})[status] += 1
                if status == "added":
                    print(f"  + {hit[0]} | {hit[1]} | {outlet}")
    print("\nSummary")
    for outlet, t in sorted(totals.items()):
        print(f"  {outlet}: {t['added']} new, {t['known']} already in the finder")
    with get_conn() as conn:
        ep.decide_patches(conn)


if __name__ == "__main__":
    main()
