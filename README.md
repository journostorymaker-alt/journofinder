# JournoFinder — UK Press Contacts Database

A self-hosted scraping tool that builds a searchable database of UK journalists across national, regional, local and specialist outlets, with email guessing and Outlook-friendly export.

Built for press and media work where you need to reach genuine local reporters in specific geographies — not the national circuit, not syndicated wire bylines.

## What it does

- **Scrapes ~160 UK outlets** across all of Great Britain (national, regional, local, hyperlocal, specialist) on a daily schedule
- **Distinguishes local staff from network reporters** by analysing how each byline is spread across outlets and regions
- **Generates email addresses** from known outlet patterns (e.g. `firstname.lastname@reachplc.com`) with confidence flags
- **Tags journalists with specialisms** (environment, agriculture, fisheries, crime, etc.) inferred from their bylines
- **Tracks newsroom-level contacts** (newsdesk@, planning@, environment@) where they're publicly listed
- **Exports to Outlook-compatible CSV** with one click — filtered to whatever subset you've selected

## How it's structured

```
journofinder/
├── scraper/
│   ├── outlets.py          # Seed list of 160 UK outlets with email patterns
│   ├── db.py               # SQLite schema and connection helpers
│   ├── scrape.py           # The actual scraper (RSS + article pages)
│   ├── consolidate.py      # Dedup, classify, generate emails
│   └── test_consolidation.py  # Sanity-check the classification logic
├── data/
│   └── journalists.db      # SQLite database (committed to repo, updated nightly)
├── dashboard/
│   └── index.html          # Self-contained HTML dashboard (sql.js)
├── .github/workflows/
│   └── scrape.yml          # GitHub Actions schedule
├── build_dashboard.sh      # Copies DB into dashboard folder for deployment
└── README.md
```

## Setup

### One-time

1. **Create a GitHub repo** and push this code. Public repos get unlimited Actions minutes; private repos get 2,000/month, plenty for this.

2. **Test locally first** to be sure things work and avoid noisy first-run failures in CI:
   ```bash
   pip install requests beautifulsoup4 feedparser
   cd scraper
   python db.py                  # initialise empty DB
   python scrape.py 5            # scrape just 5 outlets to test
   python consolidate.py         # run classification
   ```

3. **Deploy the dashboard.** Two easy options:
   - **GitHub Pages**: enable Pages on the repo, point it at the `dashboard/` folder. After each scrape, run `./build_dashboard.sh` to copy the DB across (or add this as a step in the workflow).
   - **Netlify**: connect the repo, set publish directory to `dashboard`, build command to `bash build_dashboard.sh`. Done.

4. **Once you've confirmed the workflow runs**, the GitHub Action will scrape daily at 04:00 UTC and commit the updated database back to the repo. The dashboard will automatically pick up the latest database on next page load.

### Running scrapes manually

```bash
# Full scrape of all outlets (~30-90 min depending on response times)
python scraper/scrape.py

# Quick test — just first N outlets
python scraper/scrape.py 10

# After scraping, run consolidation to classify and generate emails
python scraper/consolidate.py

# Build the dashboard bundle for deployment
./build_dashboard.sh
```

## Using the dashboard

1. Open the dashboard URL.
2. Filter by region, tier (national/regional/local), classification (local staff vs network reporter), specialism, or full-text search.
3. The **classification** filter is the key one: setting it to `local_staff` filters out journalists whose bylines are syndicated across many Reach plc or Newsquest titles, leaving you with reporters genuinely embedded in one geography.
4. Click **Export CSV (Outlook)** to download your filtered list with the columns Outlook's import wizard expects: First Name, Last Name, E-mail Address, Company, Job Title, Categories, Notes.
5. In Outlook, go to File → Open & Export → Import/Export → Import from another program → CSV → choose Contacts as destination.
6. Or use **Copy emails** to grab a semicolon-separated list ready to paste into a To/BCC field.

## How to read the email confidence flags

| Flag | Meaning |
|---|---|
| `verified` | We saw this email actually published on the outlet's website |
| `pattern_high` | The outlet has a single dominant email pattern, this is it |
| `pattern_med` | The outlet uses multiple patterns; this is one of them |
| `guess` | Falling back to common UK newsroom patterns; verify before sending sensitive material |

A `pattern_high` guess will be right for most journalists at large groups (Reach, Newsquest, National World) because they have rigorously consistent patterns. Smaller independents and broadcasters are more variable.

## How to read the classification flags

| Flag | Meaning | When to target them |
|---|---|---|
| `local_staff` | 70%+ of bylines on one local/regional outlet | Local stories, local angles on national stories |
| `regional_staff` | Bylines spread across one group's titles within one region | Regional stories, group-wide pickups |
| `network_reporter` | Bylines spread across many regions in one group (e.g. Reach plc network reporter) | National-flavour stories — these usually push out content across many titles, but the local angle won't matter to them |
| `national` | Primary outlet is national tier | National coverage |
| `unclear` | Not enough byline data yet to classify | Treat with caution |

## Important caveats

**Legal.** Scraping public-facing news sites for journalist contact information sits in a defensible grey area: bylines are published by design, and using them for legitimate press/PR contact is conventional industry practice. Most outlets prohibit automated scraping in their ToS, however. The scraper here is deliberately polite (2-second delays per domain, 30-article cap per outlet, robots.txt respected, 24h caching) but you should not push it harder. If you need higher volumes, talk to Press Gazette, Roxhill, or Cision.

**Email guesses are guesses.** Pattern-guessed emails will hit a dead letter office about 10-30% of the time depending on the outlet. If you're sending a serious tip or sensitive material, verify first by sending a low-stakes "noticed your piece on X, would love to chat" first, or use Hunter.io / similar to verify.

**Network reporter detection needs data to work.** The "local vs syndicated" distinction relies on having seen multiple bylines from the same person. After the first scrape, classification will be rough; after a few weeks of daily scrapes it gets sharp.

**Some outlets will block you.** Reach plc and DMG sites occasionally return 403/429 to scrapers. The scraper logs failures and just moves on. If a particular outlet shows zero bylines after a few runs, you may need to add a custom adapter for it.

**The seed list is editable.** `scraper/outlets.py` is just a Python list. To add a new outlet, copy an existing entry and edit. To fix a wrong email pattern, edit and re-run consolidate.py.

## What this doesn't do (yet)

- **Verified emails via SMTP probing.** Easy to add but slow and many domains will lie to you. Better to integrate Hunter.io or similar if you want this.
- **Twitter/Bluesky handles.** Could be scraped from author bio pages — added to the schema, just not extracted yet.
- **PR/comms contacts at organisations** — this is a journalist-side tool. For the company side, look at the GovTribe-style government registers you've used before.
- **Northern Ireland.** This is intentionally Great Britain only as you specified, but the architecture is identical if you want to extend.

## Maintenance

The scraper degrades gracefully — if an outlet changes its HTML structure, that one outlet will silently start producing zero bylines. Watch the dashboard's per-outlet stats (visible in scrape_log table) and update the byline extractor in `scrape.py` if a major outlet drops to zero.

About every 6 months, the email patterns may need updating — large groups occasionally migrate domains (Reach plc went from `trinitymirror.com` to `reachplc.com` a few years back).
