"""
Build the small database the dashboard loads.

The full database (data/journalists.db) keeps every story we have ever seen,
which is about 90% of its size. The dashboard only needs the people, their
emails, specialisms and profiles, plus a few totals. So this copies the
full database, keeps the totals in a small 'dashboard_meta' table, drops the
heavy tables, and compacts the result into docs/data/journalists.db.

Usage (from the repo root or the scraper folder):
  python scraper/build_dashboard_db.py
"""

import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "data" / "journalists.db"
DST = ROOT / "docs" / "data" / "journalists.db"


def main():
    DST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DST.with_suffix(".tmp")
    shutil.copyfile(SRC, tmp)
    c = sqlite3.connect(tmp)
    bylines = c.execute("SELECT COUNT(*) FROM bylines").fetchone()[0]
    updated = c.execute("SELECT MAX(scraped_at) FROM scrape_log WHERE outlet_id IS NOT NULL").fetchone()[0]
    c.execute("DROP TABLE IF EXISTS dashboard_meta")
    c.execute("CREATE TABLE dashboard_meta (key TEXT PRIMARY KEY, value TEXT)")
    c.executemany("INSERT INTO dashboard_meta VALUES (?, ?)",
                  [("bylines", str(bylines)), ("updated", updated or "")])
    c.execute("DROP TABLE IF EXISTS bylines")
    c.execute("DROP TABLE IF EXISTS scrape_log")
    c.commit()
    c.execute("VACUUM")
    c.close()
    tmp.replace(DST)
    print(f"Dashboard database: {DST.stat().st_size / 1e6:.1f} MB "
          f"(full database {SRC.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
