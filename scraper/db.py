"""
Database schema and connection helpers.

The schema is deliberately denormalised in a few places (region cached on
journalist, syndication signals computed and stored) so the dashboard can
query fast without joins.

Confidence levels for emails:
  verified     - we found this email actually published on the site
  pattern_high - outlet has a known, well-tested pattern and we matched it
  pattern_med  - outlet has a known pattern but multiple options
  guess        - we're falling back to common UK newsroom patterns
  unknown      - no name to work with (e.g. "Newsdesk")
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "journalists.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS outlets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    tier TEXT NOT NULL,
    region TEXT NOT NULL,
    group_name TEXT,
    email_pattern TEXT,
    last_scraped TIMESTAMP,
    last_scrape_status TEXT,
    last_scrape_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS journalists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    name_normalised TEXT NOT NULL,  -- for dedup: lowercase, no punctuation
    first_name TEXT,
    last_name TEXT,
    bio TEXT,
    twitter TEXT,
    -- The "primary" outlet is the one where this byline appears most often.
    -- Used for the export "Company" column and email pattern selection.
    primary_outlet_id INTEGER,
    -- Cached aggregates, refreshed by the consolidation job:
    primary_region TEXT,
    primary_tier TEXT,
    total_bylines INTEGER DEFAULT 0,
    distinct_outlets INTEGER DEFAULT 0,
    distinct_groups INTEGER DEFAULT 0,
    -- Syndication score: 0 = clearly local staff, 100 = clearly syndicated/network.
    -- Computed from the spread of bylines across outlets vs concentration on one.
    syndication_score INTEGER DEFAULT 0,
    classification TEXT,  -- 'local_staff', 'regional_staff', 'network_reporter', 'national', 'freelance', 'unclear'
    last_active_outlet_id INTEGER,  -- where most recent bylines are concentrated
    moved_from_outlet_id INTEGER,  -- if this differs from primary, journalist may have moved
    days_since_last_byline INTEGER,  -- cached for dashboard sort
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name_normalised, primary_outlet_id),
    FOREIGN KEY (primary_outlet_id) REFERENCES outlets(id)
);

CREATE INDEX IF NOT EXISTS idx_journalists_name ON journalists(name_normalised);
CREATE INDEX IF NOT EXISTS idx_journalists_region ON journalists(primary_region);
CREATE INDEX IF NOT EXISTS idx_journalists_classification ON journalists(classification);

CREATE TABLE IF NOT EXISTS journalist_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journalist_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    confidence TEXT NOT NULL,  -- verified, pattern_high, pattern_med, guess
    source TEXT,  -- url where verified, or 'pattern:reachplc.com' etc.
    is_primary INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(journalist_id, email),
    FOREIGN KEY (journalist_id) REFERENCES journalists(id)
);

CREATE INDEX IF NOT EXISTS idx_emails_journalist ON journalist_emails(journalist_id);

-- Each byline observation: every time we see a name on an article.
-- We keep these separate from journalists because the same name can appear
-- on multiple outlets and we want to track the spread.
CREATE TABLE IF NOT EXISTS bylines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journalist_id INTEGER NOT NULL,
    outlet_id INTEGER NOT NULL,
    article_url TEXT,
    article_title TEXT,
    article_date TEXT,  -- ISO date if we can parse it
    section TEXT,  -- 'news', 'sport', 'politics' etc., from URL or page metadata
    keywords TEXT,  -- comma-separated topic tags extracted from the article
    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(journalist_id, outlet_id, article_url),
    FOREIGN KEY (journalist_id) REFERENCES journalists(id),
    FOREIGN KEY (outlet_id) REFERENCES outlets(id)
);

CREATE INDEX IF NOT EXISTS idx_bylines_journalist ON bylines(journalist_id);
CREATE INDEX IF NOT EXISTS idx_bylines_outlet ON bylines(outlet_id);
CREATE INDEX IF NOT EXISTS idx_bylines_date ON bylines(article_date);

-- Specialisms inferred from byline keywords. Refreshed by consolidation.
CREATE TABLE IF NOT EXISTS journalist_specialisms (
    journalist_id INTEGER NOT NULL,
    specialism TEXT NOT NULL,
    score INTEGER NOT NULL,  -- count of bylines tagged with this topic
    PRIMARY KEY (journalist_id, specialism),
    FOREIGN KEY (journalist_id) REFERENCES journalists(id)
);

-- Newsroom-level contacts (newsdesk@, planning@) separate from journalists.
CREATE TABLE IF NOT EXISTS newsroom_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outlet_id INTEGER NOT NULL,
    role TEXT NOT NULL,  -- 'newsdesk', 'planning', 'tips', 'editor', 'environment_desk' etc.
    contact_name TEXT,  -- if known
    email TEXT,
    phone TEXT,
    confidence TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(outlet_id, role, email),
    FOREIGN KEY (outlet_id) REFERENCES outlets(id)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outlet_id INTEGER,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    url TEXT,
    status TEXT,  -- 'ok', 'http_error', 'parse_error', 'blocked', 'no_bylines'
    bylines_found INTEGER DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (outlet_id) REFERENCES outlets(id)
);
"""


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables. Idempotent."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def sync_outlets(outlets_list):
    """Sync the seed list into the outlets table.
    
    Updates existing rows by name (so changing email_pattern in seed list
    propagates), inserts new ones. Doesn't delete — outlets that go offline
    just stop being scraped, we don't lose their journalist data.
    """
    with get_conn() as conn:
        for o in outlets_list:
            conn.execute("""
                INSERT INTO outlets (name, domain, tier, region, group_name, email_pattern)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    domain=excluded.domain,
                    tier=excluded.tier,
                    region=excluded.region,
                    group_name=excluded.group_name,
                    email_pattern=excluded.email_pattern
            """, (o["name"], o["domain"], o["tier"], o["region"], o["group"], o["email_pattern"]))


if __name__ == "__main__":
    init_db()
    from outlets import OUTLETS
    sync_outlets(OUTLETS)
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM outlets").fetchone()[0]
        print(f"Database initialised at {DB_PATH}")
        print(f"Outlets in DB: {n}")
