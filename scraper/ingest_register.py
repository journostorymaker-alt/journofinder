"""
ingest_register.py
==================

One-off script to ingest the UK Parliament Register of Journalists' Interests
into the JournoFinder database. Adds ~430 Westminster lobby pass holders.

WHAT THIS SCRIPT DOES:
  1. Creates ~31 new outlets in the database for publications that weren't
     in the seed list (Politico UK, LabourList, New Statesman, etc).
  2. Updates email patterns for 4 existing outlets where verified addresses
     showed our pattern was wrong (Sky → @sky.uk, Sun → @the-sun.co.uk,
     Mail → mailonline+dailymail dual, PA → @pa.media).
  3. For each of the 430 Register journalists:
        - if they already exist in the database (matched by normalised name),
          enrich their existing record with the Register tag and email.
        - if they don't exist, insert a new journalist record with the
          Register-derived outlet, email, and tag.
  4. Tags every Register journalist with specialism "westminster_lobby" so
     they can be filtered in the dashboard.

WHAT IT DOES NOT DO:
  - It does not delete or modify existing bylines, classifications, or
    other tracked data on existing journalists. Their existing record is
    left intact, just enriched.
  - It does not re-run the classifier. New journalists from the Register
    will be classified as 'unclear' until bylines accumulate. That's correct
    behaviour — having a Westminster pass tells us nothing about the outlet
    where they actually file most.

HOW TO RUN IT:
  Place this file alongside register_data.json in the scraper/ folder of
  your repo, then run:

      cd scraper
      python ingest_register.py

  It works on a COPY of the database — original is left alone until you
  approve the result.

  After running, inspect the output, then if happy:
      mv journalists.db journalists.db.backup-pre-register
      mv journalists.db.new journalists.db
"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from shutil import copyfile


SCRIPT_DIR = Path(__file__).parent
SOURCE_DB = SCRIPT_DIR.parent / "data" / "journalists.db"
TARGET_DB = SCRIPT_DIR.parent / "data" / "journalists.db.new"
REGISTER_DATA = SCRIPT_DIR / "register_data.json"


def normalise(name: str) -> str:
    """Lowercase and strip punctuation for fuzzy name matching."""
    n = re.sub(r"[^\w\s]", "", name.lower())
    return re.sub(r"\s+", " ", n).strip()


# ============================================================
# OUTLET PLAN — what canonical Register outlet maps to what
# database outlet, plus any email-pattern updates.
# ============================================================

OUTLET_PLAN = [
    # canonical_name, existing_id_or_None, update_pattern_or_None, new_outlet_dict_or_None
    # Use existing 'BBC News' outlet id=16 — already has 104 journalists linked,
    # already at bbc.co.uk with @bbc.co.uk|@bbc.com email pattern. No changes needed.
    ("BBC News (Westminster/Politics)", 16, None, None),
    ("ITV News (via ITN)", None, None,
     {"name": "ITN — ITV News", "domain": "itn.co.uk",
      "tier": "national", "region": "UK", "group_name": "ITN",
      "email_pattern": "{first}.{last}@itn.co.uk"}),
    ("Channel 4 News (via ITN)", None, None,
     {"name": "ITN — Channel 4 News", "domain": "itn.co.uk",
      "tier": "national", "region": "UK", "group_name": "ITN",
      "email_pattern": "{first}.{last}@itn.co.uk"}),
    ("Sky News",                 19,    "{first}.{last}@sky.uk", None),
    ("The Guardian/Observer",    1,     None, None),
    ("The Times / Times Radio (News UK)", 2, None, None),
    ("The Sunday Times",         3,     None, None),
    ("The Sun / Sun on Sunday",  9,     "{first}.{last}@the-sun.co.uk", None),
    ("TalkTV (News UK)",         22,    None, None),
    ("The Telegraph",            4,     None, None),
    ("Daily Mail / Mail on Sunday", 7,
     "{first}.{last}@mailonline.co.uk|{first}.{last}@dailymail.co.uk", None),
    ("Daily Mirror / Sunday Mirror", 8, None, None),
    ("Daily Express / Sunday Express", 10, None, None),
    ("Financial Times",          12,    None, None),
    ("The Independent",          5,     None, None),
    ("The i Paper",              6,     None, None),
    ("GB News",                  20,    None, None),
    ("LBC (Global Radio)", None, None,
     {"name": "LBC (Global)", "domain": "global.com",
      "tier": "broadcast", "region": "UK", "group_name": "Global",
      "email_pattern": "{first}.{last}@global.com"}),
    ("PA Media", 159, "{first}.{last}@pa.media", None),
    ("Politico (UK)", None, None,
     {"name": "Politico (UK)", "domain": "politico.eu",
      "tier": "specialist", "region": "UK", "group_name": "Politico",
      "email_pattern": "{first}{last}@politico.eu|{first}.{last}@politico.eu"}),
    ("Dods Group (PoliticsHome / The House)", None, None,
     {"name": "Dods Group (PoliticsHome / The House)", "domain": "politicshome.com",
      "tier": "specialist", "region": "UK", "group_name": "Dods",
      "email_pattern": "{first}.{last}@dodsgroup.com|{first}.{last}@politicshome.com"}),
    ("New Statesman", None, None,
     {"name": "New Statesman", "domain": "newstatesman.co.uk",
      "tier": "national", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@newstatesman.co.uk"}),
    ("The Spectator", None, None,
     {"name": "The Spectator", "domain": "spectator.co.uk",
      "tier": "national", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@spectator.co.uk"}),
    ("The Critic", None, None,
     {"name": "The Critic", "domain": "thecritic.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "editorial@thecritic.co.uk"}),
    ("UnHerd", None, None,
     {"name": "UnHerd", "domain": "unherd.com",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@unherd.com"}),
    ("Guido Fawkes / Order Order", None, None,
     {"name": "Guido Fawkes (Order-Order)", "domain": "order-order.com",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "tips@order-order.com"}),
    ("Byline Times", 156, None, None),
    ("openDemocracy", 155, None, None),
    ("Declassified UK", None, None,
     {"name": "Declassified UK", "domain": "declassifieduk.org",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}@declassifieduk.org"}),
    ("Tribune Magazine", None, None,
     {"name": "Tribune Magazine", "domain": "tribunemag.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "editorial@tribunemag.co.uk"}),
    ("LabourList", None, None,
     {"name": "LabourList", "domain": "labourlist.org",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@labourlist.org"}),
    ("HuffPost UK", None, None,
     {"name": "HuffPost UK", "domain": "huffpost.com",
      "tier": "national", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@huffpost.com"}),
    ("Tortoise Media", None, None,
     {"name": "Tortoise Media", "domain": "tortoisemedia.com",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@tortoisemedia.com"}),
    ("Prospect Magazine", None, None,
     {"name": "Prospect Magazine", "domain": "prospectmagazine.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@prospectmagazine.co.uk"}),
    ("The Economist", None, None,
     {"name": "The Economist", "domain": "economist.com",
      "tier": "national", "region": "UK", "group_name": None,
      "email_pattern": "{first}{last}@economist.com"}),
    ("The Jewish Chronicle", None, None,
     {"name": "The Jewish Chronicle", "domain": "thejc.com",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@thejc.com"}),
    ("Jewish News", None, None,
     {"name": "Jewish News", "domain": "jewishnews.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}@jewishnews.co.uk"}),
    ("The Muslim News", None, None,
     {"name": "The Muslim News", "domain": "muslimnews.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "info@muslimnews.co.uk"}),
    ("STV News", 32, None, None),
    ("The National (Scotland)", 25, None, None),
    ("The Scotsman", 24, None, None),
    ("Daily Record (Scotland)", 26, None, None),
    ("Media Wales (Reach)", 42, None, None),
    ("Evening Standard", 116, None, None),
    ("Metro", 14, None, None),
    # MyLondon already exists at id=117 with the right Reach domain and pattern.
    ("MyLondon (Reach)", 117, None, None),
    ("Politics.co.uk", None, None,
     {"name": "Politics.co.uk", "domain": "politics.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@politics.co.uk"}),
    ("JOE Media", None, None,
     {"name": "JOE Media", "domain": "joe.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@joe.co.uk"}),
    ("Goalhanger Podcasts", None, None,
     {"name": "Goalhanger Podcasts", "domain": "goalhangerpodcasts.com",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "info@goalhangerpodcasts.com"}),
    ("DQ Magazine", None, None,
     {"name": "DQ Magazine", "domain": "dq-magazine.co.uk",
      "tier": "specialist", "region": "UK", "group_name": None,
      "email_pattern": "editor@dq-magazine.co.uk"}),
    ("Bauer Media", None, None,
     {"name": "Bauer Media", "domain": "bauermedia.co.uk",
      "tier": "broadcast", "region": "UK", "group_name": "Bauer",
      "email_pattern": "{first}.{last}@bauermedia.co.uk"}),
    ("Mentorn Media", None, None,
     {"name": "Mentorn Media", "domain": "mentorn.tv",
      "tier": "broadcast", "region": "UK", "group_name": None,
      "email_pattern": "info@mentorn.tv"}),
    ("BFBS", None, None,
     {"name": "BFBS", "domain": "bfbs.com",
      "tier": "broadcast", "region": "UK", "group_name": None,
      "email_pattern": "{first}.{last}@bfbs.com"}),
    # Morning Star already exists at id=15. Update pattern from generic newsdesk@
    # to a per-journalist pattern with newsdesk@ as fallback.
    ("Morning Star", 15,
     "{first}.{last}@peoples-press.com|newsdesk@peoples-press.com", None),
    ("National World plc", None, None,
     {"name": "National World plc", "domain": "nationalworld.com",
      "tier": "regional", "region": "UK", "group_name": "National World",
      "email_pattern": "{first}.{last}@nationalworld.com"}),
]


def generate_email(first: str, last: str, pattern: str) -> str | None:
    """Apply email pattern, keeping hyphens but stripping apostrophes/spaces.
    Returns the FIRST (primary) pattern only — others are saved separately."""
    if not first or not last or not pattern:
        return None
    f = re.sub(r"[^a-z\-]", "", first.lower())
    l = re.sub(r"[^a-z\-]", "", last.lower())
    if not f or not l:
        return None
    primary = pattern.split("|")[0].strip()
    return (primary
            .replace("{first}", f).replace("{last}", l)
            .replace("{f}", f[0]).replace("{l}", l[0]))


def generate_all_emails(first: str, last: str, pattern: str) -> list:
    """Apply ALL alternative patterns separated by | — returns list of emails."""
    if not first or not last or not pattern:
        return []
    f = re.sub(r"[^a-z\-]", "", first.lower())
    l = re.sub(r"[^a-z\-]", "", last.lower())
    if not f or not l:
        return []
    out = []
    for raw in pattern.split("|"):
        p = raw.strip()
        email = (p.replace("{first}", f).replace("{last}", l)
                  .replace("{f}", f[0]).replace("{l}", l[0]))
        if email:
            out.append(email)
    return out


def main():
    if not REGISTER_DATA.exists():
        print(f"ERROR: cannot find {REGISTER_DATA}")
        print("Make sure register_data.json is in the same folder as this script.")
        return

    if not SOURCE_DB.exists():
        print(f"ERROR: cannot find {SOURCE_DB}")
        return

    # Always work on a copy
    print(f"Copying {SOURCE_DB} → {TARGET_DB}")
    copyfile(SOURCE_DB, TARGET_DB)

    with open(REGISTER_DATA) as f:
        register = json.load(f)
    print(f"Loaded {len(register)} Register journalists")

    conn = sqlite3.connect(TARGET_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Build canonical name → outlet_id mapping
    canonical_to_outlet_id = {}

    print("\n=== STEP 1: Creating new outlets and updating existing ones ===\n")
    new_outlets_created = 0
    patterns_updated = 0

    for canonical_name, existing_id, update_pattern, new_outlet in OUTLET_PLAN:
        if existing_id is not None:
            # Use existing outlet
            row = conn.execute("SELECT id, name, email_pattern FROM outlets WHERE id = ?",
                               (existing_id,)).fetchone()
            if not row:
                print(f"  WARNING: existing_id={existing_id} not found for '{canonical_name}'")
                continue
            canonical_to_outlet_id[canonical_name] = existing_id
            if update_pattern and row['email_pattern'] != update_pattern:
                conn.execute("UPDATE outlets SET email_pattern = ? WHERE id = ?",
                             (update_pattern, existing_id))
                print(f"  ✎ UPDATED outlet {existing_id} '{row['name']}' email_pattern → {update_pattern}")
                patterns_updated += 1
        else:
            # First check whether an outlet with the same name already exists.
            # This handles the case where this script has been run before and
            # created the outlets — we should reuse them rather than crash on
            # the UNIQUE constraint.
            existing_by_name = conn.execute(
                "SELECT id, name, email_pattern FROM outlets WHERE name = ?",
                (new_outlet['name'],)
            ).fetchone()
            if existing_by_name:
                canonical_to_outlet_id[canonical_name] = existing_by_name['id']
                # If the email pattern in the existing record differs from the one
                # we'd set, update it to match our plan
                if existing_by_name['email_pattern'] != new_outlet['email_pattern']:
                    conn.execute("UPDATE outlets SET email_pattern = ? WHERE id = ?",
                                 (new_outlet['email_pattern'], existing_by_name['id']))
                    print(f"  ↻ REUSED outlet id={existing_by_name['id']} '{new_outlet['name']}' (email pattern updated)")
                else:
                    print(f"  ↻ REUSED outlet id={existing_by_name['id']} '{new_outlet['name']}'")
            else:
                # Genuinely new — create it
                cur = conn.execute("""
                    INSERT INTO outlets (name, domain, tier, region, group_name, email_pattern)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (new_outlet['name'], new_outlet['domain'], new_outlet['tier'],
                      new_outlet['region'], new_outlet['group_name'], new_outlet['email_pattern']))
                new_id = cur.lastrowid
                canonical_to_outlet_id[canonical_name] = new_id
                print(f"  + CREATED outlet id={new_id} '{new_outlet['name']}' ({new_outlet['domain']})")
                new_outlets_created += 1

    conn.commit()
    print(f"\n  → {new_outlets_created} new outlets, {patterns_updated} email patterns updated")

    # ===========================================================
    # STEP 2: Process each Register journalist
    # ===========================================================
    print("\n=== STEP 2: Processing 430 Register journalists ===\n")

    # Pre-load existing journalist names for fast lookup
    existing_journalists = {}
    for r in conn.execute("SELECT id, full_name, name_normalised, primary_outlet_id FROM journalists").fetchall():
        existing_journalists[r['name_normalised']] = dict(r)

    journalists_enriched = 0
    journalists_inserted = 0
    westminster_specialism_added = 0
    emails_added = 0

    now = datetime.now().isoformat(sep=' ', timespec='seconds')

    for entry in register:
        canonical = entry['outlet_display_name']
        outlet_id = canonical_to_outlet_id.get(canonical)
        if not outlet_id:
            print(f"  WARNING: no outlet for canonical '{canonical}' — skipping {entry['name']}")
            continue

        first = entry['first_name']
        last = entry['last_name']
        full_name = entry['name']
        norm = normalise(full_name)

        # Look up the outlet's email pattern (canonical, not the Register's hardcoded one,
        # so any "update_pattern" we just applied is reflected here).
        outlet_row = conn.execute(
            "SELECT email_pattern, domain FROM outlets WHERE id = ?", (outlet_id,)
        ).fetchone()
        outlet_pattern = outlet_row['email_pattern']

        # Decide: enrich existing or insert new?
        if norm in existing_journalists:
            jid = existing_journalists[norm]['id']
            # Enrich — DON'T overwrite primary_outlet_id, classification, etc.
            # Just add the Westminster tag and the Register-derived email if missing.
            journalists_enriched += 1
        else:
            # Insert new journalist
            cur = conn.execute("""
                INSERT INTO journalists
                    (full_name, name_normalised, first_name, last_name,
                     primary_outlet_id, primary_tier, primary_region,
                     classification, total_bylines, distinct_outlets, distinct_groups,
                     syndication_score, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'unclear', 0, 0, 0, 0, ?, ?)
            """, (full_name, norm, first, last, outlet_id,
                  None, None, now, now))
            jid = cur.lastrowid
            # Pull tier/region from outlet
            tier_region = conn.execute(
                "SELECT tier, region FROM outlets WHERE id = ?", (outlet_id,)
            ).fetchone()
            conn.execute("""
                UPDATE journalists SET primary_tier = ?, primary_region = ?
                WHERE id = ?
            """, (tier_region['tier'], tier_region['region'], jid))
            existing_journalists[norm] = {'id': jid, 'full_name': full_name,
                                          'name_normalised': norm, 'primary_outlet_id': outlet_id}
            journalists_inserted += 1

        # Tag with westminster_lobby specialism. Use score=100 to indicate "verified externally"
        try:
            conn.execute("""
                INSERT INTO journalist_specialisms (journalist_id, specialism, score)
                VALUES (?, 'westminster_lobby', 100)
            """, (jid,))
            westminster_specialism_added += 1
        except sqlite3.IntegrityError:
            # Already has the tag — ignore
            pass

        # Add the Register-derived email at pattern_high confidence, marked from Register.
        # We add ALL emails from the pattern (e.g. for Mail, both mailonline and dailymail).
        emails_to_add = generate_all_emails(first, last, outlet_pattern)
        for i, email in enumerate(emails_to_add):
            # Check whether this exact email already exists for this journalist
            existing = conn.execute(
                "SELECT id, confidence FROM journalist_emails WHERE journalist_id = ? AND email = ?",
                (jid, email)
            ).fetchone()
            if existing:
                continue  # Don't duplicate
            conn.execute("""
                INSERT INTO journalist_emails
                    (journalist_id, email, confidence, source, is_primary, created_at)
                VALUES (?, ?, 'pattern_high', 'parliament_register_2026-04-20', ?, ?)
            """, (jid, email, 1 if i == 0 else 0, now))
            emails_added += 1

    conn.commit()

    print(f"  → {journalists_inserted} journalists inserted as new")
    print(f"  → {journalists_enriched} existing journalists enriched")
    print(f"  → {westminster_specialism_added} westminster_lobby tags added")
    print(f"  → {emails_added} Register-derived emails added")

    # =========================================================
    # STEP 3: Print classification summary so user can see it worked
    # =========================================================
    print("\n=== STEP 3: Final state of database ===\n")
    rows = conn.execute("SELECT classification, COUNT(*) as n FROM journalists GROUP BY classification").fetchall()
    print("Classification counts:")
    for r in rows:
        print(f"  {r['classification'] or '(none)'}: {r['n']}")

    n_lobby = conn.execute(
        "SELECT COUNT(*) FROM journalist_specialisms WHERE specialism = 'westminster_lobby'"
    ).fetchone()[0]
    print(f"\n  Total westminster_lobby tagged: {n_lobby}")
    print(f"  Total journalists in DB: {conn.execute('SELECT COUNT(*) FROM journalists').fetchone()[0]}")
    print(f"  Total outlets in DB: {conn.execute('SELECT COUNT(*) FROM outlets').fetchone()[0]}")

    conn.close()
    print(f"\nDone. New database is at: {TARGET_DB}")
    print("\nTo apply:")
    print(f"  mv {SOURCE_DB} {SOURCE_DB}.backup-pre-register")
    print(f"  mv {TARGET_DB} {SOURCE_DB}")


if __name__ == "__main__":
    main()
