"""
Consolidation: turn raw byline observations into clean journalist profiles.

Run this AFTER scrape.py. It does four things:

1. Cross-outlet dedup. The same byline on Yorkshire Post and Sheffield Star
   might be one person. We merge based on identical normalised name + same
   group_name. We do NOT merge across groups (Sarah Smith at Reach is
   probably a different person from Sarah Smith at News UK).

2. Classification. We label each journalist as:
     - 'local_staff'      -- 80%+ of bylines on one local/regional outlet
     - 'regional_staff'   -- bylines spread across one group's titles in one region
     - 'network_reporter' -- bylines spread across one group's titles in many regions
     - 'national'         -- primary outlet is national tier
     - 'unclear'          -- not enough data
   This is the key signal for filtering "real local journalists" in the dashboard.

3. Email generation. Apply the outlet's known pattern to first/last name,
   then add fallback guesses with lower confidence. We never claim to have
   verified an email unless we actually saw it on a page.

4. Specialisms. Aggregate keywords across each journalist's bylines.

This is run separately from scraping so it's cheap to re-run as we tune
the classification logic without re-scraping.
"""

from collections import Counter, defaultdict
from db import get_conn
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


def _generate_emails(first, last, pattern_str, fallback_domain=None):
    """Return list of (email, confidence) tuples."""
    emails = []
    
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
    
    Looks at all bylines for this journalist (by normalised name across all
    outlets in their primary group), counts how spread they are.
    """
    # Get all bylines for this journalist
    rows = conn.execute("""
        SELECT b.outlet_id, o.name, o.tier, o.region, o.group_name, COUNT(*) as n
        FROM bylines b
        JOIN outlets o ON b.outlet_id = o.id
        WHERE b.journalist_id = ?
        GROUP BY b.outlet_id
    """, (jid,)).fetchall()
    
    if not rows:
        return "unclear", 0, 0, 0, 0, None, None
    
    total_bylines = sum(r["n"] for r in rows)
    distinct_outlets = len(rows)
    distinct_groups = len(set(r["group_name"] for r in rows if r["group_name"]))
    distinct_regions = len(set(r["region"] for r in rows if r["region"]))
    
    # Identify primary outlet (most bylines)
    primary = max(rows, key=lambda r: r["n"])
    primary_share = primary["n"] / total_bylines
    
    # Syndication score: 0 = totally concentrated, 100 = totally spread
    if total_bylines == 0:
        synd = 0
    else:
        # Use Herfindahl-style concentration index, inverted
        shares = [r["n"] / total_bylines for r in rows]
        concentration = sum(s * s for s in shares)
        synd = int(round((1 - concentration) * 100))
    
    # Classification logic
    if primary["tier"] == "national":
        classification = "national"
    elif distinct_regions >= 4 and distinct_outlets >= 4:
        # Bylines spread across many regions = clearly a network reporter
        classification = "network_reporter"
    elif distinct_outlets >= 3 and distinct_groups == 1:
        # Same group, multiple titles, fewer regions = regional staff
        classification = "regional_staff"
    elif primary_share >= 0.7 and distinct_outlets <= 2:
        # Concentrated on one outlet = local staff
        classification = "local_staff"
    elif distinct_outlets <= 2:
        classification = "local_staff"
    else:
        classification = "unclear"
    
    return (classification, total_bylines, distinct_outlets, distinct_groups, synd,
            primary["name"], primary["region"])


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
        journalists = conn.execute("SELECT id, first_name, last_name FROM journalists").fetchall()
        print(f"  Processing {len(journalists)} journalists...")
        
        for j in journalists:
            jid = j["id"]
            
            # Classify
            (classification, total, n_outlets, n_groups, synd, primary_name, primary_region) = (
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
                    primary_tier = ?
                WHERE id = ?
            """, (classification, total, n_outlets, n_groups, synd, primary_region, primary_tier, jid))
            
            # Specialisms
            conn.execute("DELETE FROM journalist_specialisms WHERE journalist_id = ?", (jid,))
            for spec, count in _extract_specialisms(jid, conn).most_common(5):
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
