"""
Consolidation: turn raw byline observations into clean journalist profiles.

Run this AFTER scrape.py. It does four things:

1. Cross-outlet dedup. The same byline on Yorkshire Post and Sheffield Star
   might be one person. We merge based on identical normalised name + same
   group_name. We do NOT merge across groups (Sarah Smith at Reach is
   probably a different person from Sarah Smith at News UK).

2. Classification. We label each journalist as:
     - 'local_staff'      -- bylines dominated by one outlet, or all from a single outlet
     - 'regional_staff'   -- bylines spread across one publisher group's titles
     - 'network_reporter' -- bylines genuinely scattered across multiple unrelated groups
     - 'national'         -- primary outlet is national tier
     - 'unclear'          -- not enough data, or no clear pattern

   The classifier groups bylines by *publisher group* first (Newsquest, Reach,
   BBC, etc), then looks at outlet dominance within that group. This stops a
   Brighton Argus reporter being mislabelled "network reporter" just because
   Newsquest's CMS auto-syndicates her stories across sister titles.

3. Email generation. Apply the outlet's known pattern to first/last name,
   then add fallback guesses with lower confidence. We never claim to have
   verified an email unless we actually saw it on a page.

4. Specialisms. Aggregate keywords across each journalist's bylines.
   Note: byline-derived specialisms use scores in the 1-99 range (literally
   the keyword count). Externally-added tags (e.g. 'westminster_lobby' from
   the Parliament Register ingestion) use score=100 so they survive the
   rebuild step below.

This is run separately from scraping so it's cheap to re-run as we tune
the classification logic without re-scraping.
"""

from collections import Counter, defaultdict
from pathlib import Path
from db import get_conn


# Load excluded names — guest contributors who aren't journalists
# (MPs, academics, activists who byline op-eds at outlets like Byline Times,
# openDemocracy, The Canary, Morning Star).
def _load_excluded_names():
    """Returns a set of normalised names to exclude from journalist records."""
    exclude_file = Path(__file__).parent / "excluded_names.txt"
    excluded = set()
    if exclude_file.exists():
        for line in exclude_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Normalise: lowercase, strip post-nominals
            import re
            n = re.sub(r"[^\w\s]", "", line.lower())
            n = re.sub(r"\s+", " ", n).strip()
            # Strip post-nominals like "MP", "OBE" (same logic as scrape.py)
            POST_NOMINALS = {"mp", "msp", "ms", "mep", "am", "obe", "cbe", "mbe",
                             "kbe", "dbe", "phd", "md", "qc", "kc", "rev", "revd",
                             "bsc", "ba", "ma", "msc", "mba", "llb", "llm", "jr", "sr"}
            parts = n.split()
            while len(parts) > 2 and parts[-1] in POST_NOMINALS:
                parts.pop()
            excluded.add(" ".join(parts))
    return excluded


EXCLUDED_NAMES = _load_excluded_names()
from outlets import OUTLETS

# Keep first letter case-aware lookups
OUTLET_BY_NAME = {o["name"]: o for o in OUTLETS}


def _format_pattern(pattern, first, last):
    """Apply a pattern template to a name. Returns None if name parts missing."""
    if not first or not last:
        return None
    f = first.lower().strip()
    l = last.lower().strip()
    # Strip non-alpha (apostrophes, hyphens) for email locals
    f_clean = "".join(c for c in f if c.isalpha())
    l_clean = "".join(c for c in l if c.isalpha())
    if not f_clean or not l_clean:
        return None
    
    return (pattern
        .replace("{first.last}", f"{f_clean}.{l_clean}")
        .replace("{firstlast}", f"{f_clean}{l_clean}")
        .replace("{first}", f_clean)
        .replace("{last}", l_clean)
        .replace("{f}", f_clean[0])
        .replace("{l}", l_clean[0])
    )


NEWSROOM_PATTERN_LOCALS = {
    "newsdesk", "news", "tips", "tipoff",
    "editor", "editorial",
    "info", "hello", "contact",
    "letters", "comment", "press", "admin",
    "team", "office",
}


def _generate_emails(first, last, pattern_str, fallback_domain=None):
    """Return list of (email, confidence, source) tuples.
    
    If the outlet's email_pattern is a generic newsroom-style address that
    doesn't substitute {first}/{last}, return empty list. We don't want to
    assign newsdesk@ to individual journalists; that's a newsroom contact,
    not a personal email.
    """
    emails = []
    
    # Detect generic newsroom-style patterns and refuse to generate from them
    if pattern_str and pattern_str != "unknown":
        first_pattern = pattern_str.split("|")[0].strip()
        # If pattern has no name placeholder, it's a generic email
        if "{" not in first_pattern:
            # Check if local part is a newsroom term
            if "@" in first_pattern:
                local = first_pattern.split("@")[0].lower().strip()
                if local in NEWSROOM_PATTERN_LOCALS:
                    return []  # don't assign newsroom email to a journalist
    
    if pattern_str and pattern_str != "unknown":
        # Pattern can have multiple alternatives separated by |
        patterns = pattern_str.split("|")
        for i, pattern in enumerate(patterns):
            email = _format_pattern(pattern.strip(), first, last)
            if email:
                # First listed pattern is highest confidence
                conf = "pattern_high" if i == 0 else "pattern_med"
                emails.append((email, conf, f"pattern:{pattern.strip()}"))
    
    # Generic fallbacks if we have a domain
    if fallback_domain and first and last:
        f_clean = "".join(c for c in first.lower() if c.isalpha())
        l_clean = "".join(c for c in last.lower() if c.isalpha())
        if f_clean and l_clean:
            fallback_locals = [
                f"{f_clean}.{l_clean}",
                f"{f_clean[0]}.{l_clean}",
                f"{f_clean}{l_clean}",
                f"{f_clean}",
            ]
            existing_locals = {e[0].split("@")[0] for e in emails}
            existing_domains = {e[0].split("@")[1] for e in emails}
            for local in fallback_locals:
                if local not in existing_locals and fallback_domain not in existing_domains:
                    emails.append((f"{local}@{fallback_domain}", "guess", "fallback_pattern"))
                    break  # one fallback is enough
    
    return emails


def _classify_journalist(jid, conn):
    """Decide if a journalist is local_staff, network_reporter, etc.
    
    The rules walk down a list, stopping at the first match:
    
      1. national tier → 'national' (a Guardian or Mirror staffer)
      2. only 1 outlet seen → 'local_staff' (trust the single source)
      3. <3 bylines and 2+ outlets → 'unclear' (too little to call)
      4. one outlet has >=70% of bylines → 'local_staff' there
      5. one publisher group has >=80% of bylines → staff within that group
         - 'local_staff' if the dominant outlet within the group has >=50%
         - 'regional_staff' otherwise (spread across sister titles)
      6. top outlet <50% AND 2+ groups each >=25% → 'network_reporter'
         (genuinely scattered across unrelated publishers)
      7. anything else → 'unclear'
    
    Bylines are recency-weighted: last 30 days count 3x, last 30-90 days
    count 1.5x, older count 1x. This means journalists who change outlets
    get reclassified within weeks rather than being locked into their
    first observed pattern.
    
    Grouping bylines by publisher group is the key fix vs. earlier rules:
    a Brighton Argus reporter whose stories auto-syndicate to Hampshire
    Chronicle, Bournemouth Echo etc via Newsquest's shared CMS no longer
    gets mistakenly tagged as a 'network reporter' just because her bylines
    appear on multiple titles in multiple regions.
    """
    # Get all bylines with their dates
    rows = conn.execute("""
        SELECT b.outlet_id, b.seen_at, o.name, o.tier, o.region, o.group_name
        FROM bylines b
        JOIN outlets o ON b.outlet_id = o.id
        WHERE b.journalist_id = ?
    """, (jid,)).fetchall()
    
    if not rows:
        return ("unclear", 0, 0, 0, 0, None, None, None, None, None)
    
    # Compute recency-weighted byline counts per outlet AND per publisher group.
    # Bylines from the last 30 days count 3x. 30-90 days count 1.5x. Older count 1x.
    from datetime import datetime, timedelta
    now = datetime.now()
    
    outlet_weighted = {}  # outlet_id -> weighted count
    outlet_meta = {}      # outlet_id -> dict of metadata
    group_weighted = {}   # group_name -> weighted count (key fix: group-level view)
    most_recent_byline_date = None
    most_recent_outlet_id = None
    
    for r in rows:
        oid = r["outlet_id"]
        try:
            seen_at = datetime.fromisoformat(r["seen_at"])
        except (TypeError, ValueError):
            seen_at = now
        
        days_ago = (now - seen_at).days
        if days_ago < 30:
            weight = 3.0
        elif days_ago < 90:
            weight = 1.5
        else:
            weight = 1.0
        
        outlet_weighted[oid] = outlet_weighted.get(oid, 0) + weight
        outlet_meta[oid] = {
            "name": r["name"], "tier": r["tier"], "region": r["region"], "group_name": r["group_name"]
        }
        # Group-level weighting. Outlets without a group_name are bucketed alone
        # so a solo independent outlet doesn't accidentally collapse into other
        # solo independents.
        gname = r["group_name"] if r["group_name"] else f"_solo_{r['name']}"
        group_weighted[gname] = group_weighted.get(gname, 0) + weight
        
        if most_recent_byline_date is None or seen_at > most_recent_byline_date:
            most_recent_byline_date = seen_at
            most_recent_outlet_id = oid
    
    total_weighted = sum(outlet_weighted.values())
    total_bylines = len(rows)
    distinct_outlets = len(outlet_weighted)
    distinct_groups = len(set(m["group_name"] for m in outlet_meta.values() if m["group_name"]))
    distinct_regions = len(set(m["region"] for m in outlet_meta.values() if m["region"]))
    
    # Primary outlet by weighted score (so recent bylines dominate)
    primary_oid = max(outlet_weighted, key=outlet_weighted.get)
    primary_meta = outlet_meta[primary_oid]
    primary_share = outlet_weighted[primary_oid] / total_weighted if total_weighted else 0
    
    # Primary publisher group by weighted score
    primary_group = max(group_weighted, key=group_weighted.get) if group_weighted else None
    primary_group_share = group_weighted[primary_group] / total_weighted if total_weighted and primary_group else 0
    
    # Days since last byline
    days_since = (now - most_recent_byline_date).days if most_recent_byline_date else None
    
    # Syndication score (Herfindahl, on weighted shares) — kept as a useful
    # filter signal in the dashboard even though the classifier no longer uses it
    if total_weighted == 0:
        synd = 0
    else:
        shares = [w / total_weighted for w in outlet_weighted.values()]
        concentration = sum(s * s for s in shares)
        synd = int(round((1 - concentration) * 100))
    
    # ===== Classification rules (walk down, first match wins) =====
    
    # Rule 1: national outlet → 'national', regardless of share
    if primary_meta["tier"] == "national":
        classification = "national"
    
    # Rule 2: only one outlet seen → trust it (permissive single-outlet rule)
    elif distinct_outlets == 1:
        classification = "local_staff"
    
    # Rule 3: very thin evidence and multiple outlets → 'unclear'
    elif total_bylines < 3:
        classification = "unclear"
    
    # Rule 4: one outlet dominates (≥70% of weighted bylines) → 'local_staff'
    elif primary_share >= 0.70:
        classification = "local_staff"
    
    # Rule 5: one publisher group dominates (≥80%) → staff within that group
    elif primary_group_share >= 0.80:
        if primary_share >= 0.50:
            classification = "local_staff"
        else:
            classification = "regional_staff"
    
    # Rule 6: bylines genuinely scatter across multiple unrelated groups → 'network_reporter'
    # Top outlet must hold under 50% AND at least 2 groups must each hold ≥25%.
    # This catches PA Media wire reporters and similar; it does NOT catch local
    # staff whose work occasionally appears at one or two non-group outlets.
    elif primary_share < 0.50:
        big_groups = [g for g, w in group_weighted.items() if w / total_weighted >= 0.25]
        if len(big_groups) >= 2:
            classification = "network_reporter"
        else:
            classification = "unclear"
    
    # Rule 7: catch-all — middling outlet share, no clear group dominance
    else:
        classification = "unclear"
    
    # Movement detection: was the primary outlet different in older data?
    # Compare last 30 days vs the prior 30-180 days window.
    moved_from_oid = None
    recent_outlet_count = {}
    older_outlet_count = {}
    for r in rows:
        try:
            seen_at = datetime.fromisoformat(r["seen_at"])
        except (TypeError, ValueError):
            continue
        days_ago = (now - seen_at).days
        if days_ago < 30:
            recent_outlet_count[r["outlet_id"]] = recent_outlet_count.get(r["outlet_id"], 0) + 1
        elif days_ago < 180:
            older_outlet_count[r["outlet_id"]] = older_outlet_count.get(r["outlet_id"], 0) + 1
    
    if recent_outlet_count and older_outlet_count:
        recent_top = max(recent_outlet_count, key=recent_outlet_count.get)
        older_top = max(older_outlet_count, key=older_outlet_count.get)
        if recent_top != older_top and recent_outlet_count[recent_top] >= 2:
            # They've moved — recent activity is at a different outlet
            moved_from_oid = older_top
    
    return (classification, total_bylines, distinct_outlets, distinct_groups, synd,
            primary_meta["name"], primary_meta["region"],
            most_recent_outlet_id, moved_from_oid, days_since)
   

def _extract_specialisms(jid, conn):
    """Aggregate keywords from journalist's bylines."""
    rows = conn.execute("""
        SELECT keywords FROM bylines WHERE journalist_id = ? AND keywords != ''
    """, (jid,)).fetchall()
    
    counter = Counter()
    for row in rows:
        for kw in row["keywords"].split(","):
            kw = kw.strip()
            if kw:
                counter[kw] += 1
    return counter


def consolidate():
    """Run the full consolidation pass."""
    print("Consolidating journalist data...")
    
    with get_conn() as conn:
        # ===== STEP 1: Remove excluded journalists (guest contributors) =====
        if EXCLUDED_NAMES:
            removed = 0
            removed_bylines = 0
            for r in conn.execute("SELECT id, full_name, name_normalised FROM journalists").fetchall():
                if r["name_normalised"] in EXCLUDED_NAMES:
                    n_byl = conn.execute(
                        "SELECT COUNT(*) FROM bylines WHERE journalist_id = ?", (r["id"],)
                    ).fetchone()[0]
                    conn.execute("DELETE FROM bylines WHERE journalist_id = ?", (r["id"],))
                    conn.execute("DELETE FROM journalist_emails WHERE journalist_id = ?", (r["id"],))
                    conn.execute("DELETE FROM journalist_specialisms WHERE journalist_id = ?", (r["id"],))
                    conn.execute("DELETE FROM journalists WHERE id = ?", (r["id"],))
                    removed += 1
                    removed_bylines += n_byl
            if removed:
                print(f"  Removed {removed} excluded names ({removed_bylines} bylines)")
            conn.commit()
        
        journalists = conn.execute("SELECT id, first_name, last_name FROM journalists").fetchall()
        print(f"  Processing {len(journalists)} journalists...")
        
        for j in journalists:
            jid = j["id"]
            
            # Classify
            (classification, total, n_outlets, n_groups, synd, primary_name, primary_region,
             last_active_oid, moved_from_oid, days_since) = (
                _classify_journalist(jid, conn)
            )
            
            primary_tier = None
            if primary_name:
                row = conn.execute("SELECT tier FROM outlets WHERE name = ?", (primary_name,)).fetchone()
                if row:
                    primary_tier = row["tier"]
            
            conn.execute("""
                UPDATE journalists SET
                    classification = ?,
                    total_bylines = ?,
                    distinct_outlets = ?,
                    distinct_groups = ?,
                    syndication_score = ?,
                    primary_region = ?,
                    primary_tier = ?,
                    last_active_outlet_id = ?,
                    moved_from_outlet_id = ?,
                    days_since_last_byline = ?
                WHERE id = ?
            """, (classification, total, n_outlets, n_groups, synd, primary_region, primary_tier,
                  last_active_oid, moved_from_oid, days_since, jid))
            
            # Specialisms — only wipe byline-derived (low-score, <100) ones, preserving
            # externally-added high-score tags like 'westminster_lobby' (score=100) added
            # by ingestion scripts. Otherwise those tags get wiped on every scrape and
            # we lose useful filter labels.
            conn.execute("""
                DELETE FROM journalist_specialisms
                WHERE journalist_id = ? AND score < 100
            """, (jid,))
            for spec, count in _extract_specialisms(jid, conn).most_common(5):
                # Don't insert a byline-derived spec if the same name is already
                # there at score >= 100 — the high-score one stays untouched.
                existing = conn.execute("""
                    SELECT score FROM journalist_specialisms
                    WHERE journalist_id = ? AND specialism = ?
                """, (jid, spec)).fetchone()
                if existing and existing[0] >= 100:
                    continue
                conn.execute("""
                    INSERT INTO journalist_specialisms (journalist_id, specialism, score)
                    VALUES (?, ?, ?)
                """, (jid, spec, count))
            
            # Emails
            outlet = conn.execute("""
                SELECT email_pattern, domain FROM outlets WHERE id = ?
            """, (conn.execute("SELECT primary_outlet_id FROM journalists WHERE id = ?", (jid,)).fetchone()["primary_outlet_id"],)).fetchone()
            
            if outlet and j["first_name"] and j["last_name"]:
                emails = _generate_emails(
                    j["first_name"], j["last_name"],
                    outlet["email_pattern"],
                    outlet["domain"].split("/")[0],
                )
                # Don't wipe verified emails — only refresh patterns
                conn.execute("""
                    DELETE FROM journalist_emails 
                    WHERE journalist_id = ? AND confidence != 'verified'
                """, (jid,))
                for i, (email, conf, source) in enumerate(emails):
                    conn.execute("""
                        INSERT OR IGNORE INTO journalist_emails 
                            (journalist_id, email, confidence, source, is_primary)
                        VALUES (?, ?, ?, ?, ?)
                    """, (jid, email, conf, source, 1 if i == 0 else 0))
        
        # ===== STEP 2: Flag email ambiguity =====
        # When the same primary email is assigned to 2+ journalists, downgrade
        # all of them to 'guess' confidence, because we can't tell which one
        # the email actually belongs to.
        # Common cause: outlets with first-name-only patterns (Mill Media, Byline Times)
        # where two journalists share a first name.
        ambiguous_count = 0
        rows = conn.execute("""
            SELECT email, COUNT(DISTINCT journalist_id) as n_journalists
            FROM journalist_emails
            WHERE is_primary = 1 AND confidence != 'verified'
            GROUP BY email
            HAVING n_journalists > 1
        """).fetchall()
        
        for r in rows:
            email = r["email"]
            n = r["n_journalists"]
            conn.execute("""
                UPDATE journalist_emails
                SET confidence = 'guess'
                WHERE email = ? AND confidence != 'verified'
            """, (email,))
            ambiguous_count += n
        
        if ambiguous_count:
            print(f"  Flagged {len(rows)} ambiguous email addresses "
                  f"affecting {ambiguous_count} journalists (confidence -> guess)")
        
        print("  Done.")
        
        # Print summary
        rows = conn.execute("""
            SELECT classification, COUNT(*) as n FROM journalists GROUP BY classification
        """).fetchall()
        print("\nClassification breakdown:")
        for r in rows:
            print(f"  {r['classification'] or '(unclassified)'}: {r['n']}")


if __name__ == "__main__":
    consolidate()
