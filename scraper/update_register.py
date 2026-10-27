"""
Update the finder from a new edition of Parliament's Register of
Journalists' Interests (the lobby pass list).

Parliament publishes a new edition every six weeks or so. Its site blocks
automated downloads, so the PDF is downloaded by hand and run through this:

  python update_register.py path/to/register.pdf "2026-10-05"

What it does:
  - reads every journalist and their sponsor (employer) from the PDF
  - works out which outlet in the finder each sponsor is
  - adds lobby journalists who aren't in the finder yet
  - moves people whose outlet has changed (unless they have recent stories
    at their current outlet, in which case they may be a namesake)
  - tags everyone on the list "westminster_lobby"
  - for anyone on the previous edition but not this one: removes the tag
    and records that they left. They stay in the finder.
  - keeps a history in the lobby_register table
  - prints a plain report of what changed

Reading the PDF needs `pdftotext` (poppler-utils).
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scrape  # noqa: E402
from db import get_conn  # noqa: E402
import enrich_profiles as ep  # noqa: E402

LOBBY_TAG = "westminster_lobby"

LOBBY_SCHEMA = """
CREATE TABLE IF NOT EXISTS lobby_register (
    name_normalised TEXT PRIMARY KEY,
    full_name TEXT,
    sponsor TEXT,             -- employer exactly as written on the Register
    outlet TEXT,              -- the finder outlet we matched it to
    other_occupation TEXT,
    first_edition TEXT,       -- first edition we saw them on
    last_edition TEXT,        -- latest edition they were on
    status TEXT,              -- 'current' or 'left'
    left_edition TEXT         -- first edition they were missing from
);
CREATE TABLE IF NOT EXISTS lobby_editions (
    edition TEXT PRIMARY KEY,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entries INTEGER
);
"""

# Sponsor as written on the Register -> outlet name in the finder.
# Checked in order; first match wins. Anything unmatched gets its own outlet.
SPONSOR_RULES = [
    (r"BBC Scotland", "BBC Scotland"),
    (r"\bBBC\b", "BBC News"),
    (r"Channel ?4", "Channel 4 News"),
    (r"Channel ?5", "Channel 5 News"),
    (r"Good Morning Britain", "ITV Good Morning Britain"),
    (r"ITV Border", "ITV News Border"),
    (r"ITV Central", "ITV News Central"),
    (r"ITV London", "ITV News London"),
    (r"ITV Wales", "ITV Wales"),
    (r"ITV West Country", "ITV News West Country"),
    (r"ITV Anglia", "ITV News Anglia"),
    (r"ITV Granada|Granada", "ITV News Granada"),
    (r"ITV Meridian|Meridian", "ITV News Meridian"),
    (r"ITV Tyne Tees|Tyne Tees", "ITV News Tyne Tees"),
    (r"ITV Calendar|Calendar", "ITV News Calendar"),
    (r"Ulster|UTV", "UTV"),
    (r"\bITN\b|\bITV\b", "ITV News (National)"),
    (r"^Sky\b|Sky News", "Sky News"),
    (r"Sunday Times", "The Sunday Times"),
    (r"Times Radio|News UK/Times|^Times$|The Times", "The Times"),
    (r"\bTalk\b", "TalkTV"),
    (r"\bSun\b", "The Sun"),
    (r"Telegraph", "The Telegraph"),
    (r"Observer", "The Observer"),
    (r"Guardian", "The Guardian"),
    (r"Mail", "Daily Mail"),
    (r"Mirror|Sunday People", "The Mirror"),
    (r"Daily Star", "Daily Star"),
    (r"Express", "Daily Express"),
    (r"\bi Newspaper\b|\bI Newspaper\b|i Paper", "The i Paper"),
    (r"Independent", "The Independent"),
    (r"Financial Times", "Financial Times"),
    (r"Evening Standard", "Evening Standard"),
    (r"^Metro$", "Metro"),
    (r"GB News", "GB News"),
    (r"LBC|Global", "LBC (Global)"),
    (r"Press Association|PA Media", "Press Association / PA Media"),
    (r"Reuters", "Reuters UK"),
    (r"Politico", "Politico (UK)"),
    (r"PoliticsHome|Politics Home|Total Politics|The House|Dods", "Dods Group (PoliticsHome / The House)"),
    (r"ConservativeHome|Conservative Home", "ConservativeHome"),
    (r"New Statesman", "New Statesman"),
    (r"Spectator", "The Spectator"),
    (r"Economist", "The Economist"),
    (r"Prospect", "Prospect Magazine"),
    (r"UnHerd", "UnHerd"),
    (r"Byline Times", "Byline Times"),
    (r"LabourList", "LabourList"),
    (r"Guido|Order! Order|Order Order", "Guido Fawkes (Order-Order)"),
    (r"HuffPost", "HuffPost UK"),
    (r"JOE", "JOE Media"),
    (r"Goalhanger", "Goalhanger Podcasts"),
    (r"DQ Magazine", "DQ Magazine"),
    (r"Bauer", "Bauer Media"),
    (r"Mentorn", "Mentorn Media"),
    (r"BFBS|British Forces", "BFBS"),
    (r"Jewish Chronicle", "The Jewish Chronicle"),
    (r"Jewish News", "Jewish News"),
    (r"Muslim News", "The Muslim News"),
    (r"Morning Star", "Morning Star"),
    (r"Tribune", "Tribune Magazine"),
    (r"Declassified", "Declassified UK"),
    (r"Politics\.co\.uk|Politics UK", "Politics.co.uk"),
    (r"^STV", "STV News"),
    (r"Scotsman", "The Scotsman"),
    (r"^The National$|The National/Newsquest", "The National"),
    (r"Daily Record", "Daily Record"),
    (r"Edinburgh Evening News", "Edinburgh Evening News"),
    (r"South Wales Argus", "South Wales Argus"),
    (r"My ?London", "MyLondon"),
    (r"Yorkshire Post", "Yorkshire Post"),
    (r"Tortoise", "Tortoise Media"),
    (r"Media Wales", "WalesOnline"),
]

# Tidy names for outlets that appear under several spellings
FOREIGN_NAMES = {
    "Bloomberg": "Bloomberg News",
    "Agence France Presse": "AFP",
    "Thomson Reuters": "Reuters UK",
}

# Email patterns for outlets this script may need to create. Anything not
# listed gets no email guess ('unknown'), which is better than a wrong one.
NEW_OUTLET_PATTERNS = {
    "ITV Good Morning Britain": "{first}.{last}@itv.com",
    "ConservativeHome": "unknown",
    "UTV": "{first}.{last}@itv.com",
}


def outlet_for(sponsor):
    # Foreign Press Association members first, or "Press Association" in the
    # name would send them to PA Media
    m = re.search(r"Foreign Press Association \((.+)\)", sponsor) or \
        re.search(r"^(.+?) \(Foreign Press Association\)", sponsor)
    if m:
        return FOREIGN_NAMES.get(m.group(1).strip(), m.group(1).strip())
    if sponsor.strip() == "Foreign Press Association":
        return "Foreign Press Association"
    for rx, outlet in SPONSOR_RULES:
        if re.search(rx, sponsor):
            return outlet
    return FOREIGN_NAMES.get(sponsor.strip(), sponsor.strip())


def parse_pdf(pdf):
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                          capture_output=True, text=True, check=True).stdout
    rows, cols = [], None
    for ln in text.splitlines():
        if ln.strip().startswith("JOURNALIST") and "SPONSOR" in ln:
            cols = (ln.index("SPONSOR"), ln.index("OTHER RELEVANT"))
            continue
        if not cols or not ln.strip() or "PAGE " in ln or "LIST OF JOURNALISTS" in ln:
            continue
        s, o = cols
        name, sponsor, other = ln[:s].strip(), ln[s:o].strip(), ln[o:].strip()
        if name:
            parts = name.split()
            rows.append({"first": parts[0], "last": " ".join(parts[1:]),
                         "sponsor": sponsor, "other": other})
        elif rows:
            if sponsor:
                rows[-1]["sponsor"] += " " + sponsor
            if other:
                rows[-1]["other"] += " " + other
    return [r for r in rows if r["last"] and r["sponsor"]]


def ensure_outlet(conn, name):
    o = conn.execute("SELECT id, region, tier FROM outlets WHERE name = ?", (name,)).fetchone()
    if o:
        return o
    pattern = NEW_OUTLET_PATTERNS.get(name, "unknown")
    conn.execute("""INSERT INTO outlets (name, domain, tier, region, group_name, email_pattern)
                    VALUES (?, '', 'specialist', 'UK', NULL, ?)""", (name, pattern))
    return conn.execute("SELECT id, region, tier FROM outlets WHERE name = ?", (name,)).fetchone()


def same_group(a, b):
    """BBC Wales and BBC News, or ITV News Border and ITV News (National)."""
    fa, fb = a.split()[0].lower(), b.split()[0].lower()
    return fa == fb and fa in ("bbc", "itv")


def main():
    pdf, edition = Path(sys.argv[1]), sys.argv[2]
    rows = parse_pdf(pdf)
    print(f"Register of {edition}: {len(rows)} journalists")
    added, moved, kept_namesake, tagged = [], [], [], 0
    new_outlets = set()

    with get_conn() as conn:
        conn.executescript(LOBBY_SCHEMA)
        prev = conn.execute("SELECT MAX(edition) FROM lobby_editions WHERE edition < ?", (edition,)).fetchone()[0]
        seen = set()
        for r in rows:
            full = f"{r['first']} {r['last']}"
            norm = scrape._normalise_name(full)
            outlet = outlet_for(r["sponsor"])
            if not conn.execute("SELECT 1 FROM outlets WHERE name = ?", (outlet,)).fetchone():
                new_outlets.add(outlet)
            o = ensure_outlet(conn, outlet)

            j = conn.execute("SELECT j.id, j.name_normalised, o.name AS outlet FROM journalists j "
                             "JOIN outlets o ON o.id = j.primary_outlet_id WHERE j.name_normalised = ?",
                             (norm,)).fetchone()
            if not j:
                # Same person under a short first name? ("Tim Baker" for "Timothy Baker")
                for cand in conn.execute("SELECT j.id, j.name_normalised, o.name AS outlet FROM journalists j "
                                         "JOIN outlets o ON o.id = j.primary_outlet_id WHERE j.last_name = ?",
                                         (r["last"],)).fetchall():
                    if ep._same_person_name(cand["name_normalised"], norm) and \
                            (cand["outlet"] == outlet or same_group(cand["outlet"], outlet)):
                        j = cand
                        break
            if not j:
                first, last = scrape._split_name(full)
                conn.execute("""
                    INSERT INTO journalists (full_name, name_normalised, first_name, last_name,
                        primary_outlet_id, classification, total_bylines, primary_region, primary_tier)
                    VALUES (?, ?, ?, ?, ?, 'unclear', 0, ?, ?)
                """, (full, norm, first, last, o["id"], o["region"], o["tier"]))
                jid = conn.execute("SELECT id FROM journalists WHERE name_normalised = ?", (norm,)).fetchone()[0]
                added.append(f"{full} ({outlet})")
                key = norm
            else:
                jid, key = j["id"], j["name_normalised"]
                if j["outlet"] != outlet and not same_group(j["outlet"], outlet):
                    recent = conn.execute("""
                        SELECT COUNT(*) FROM bylines WHERE journalist_id = ? AND outlet_id != ?
                        AND COALESCE(NULLIF(article_date, ''), seen_at) >= date('now', '-90 days')
                    """, (jid, o["id"])).fetchone()[0]
                    cur = conn.execute("SELECT tier, group_name, region FROM outlets WHERE name = ?", (j["outlet"],)).fetchone()
                    tgt = conn.execute("SELECT group_name FROM outlets WHERE id = ?", (o["id"],)).fetchone()
                    verified_elsewhere = conn.execute("""
                        SELECT COUNT(*) FROM journalist_emails WHERE journalist_id = ? AND confidence = 'verified'
                    """, (jid,)).fetchone()[0]
                    # The Register names their employer, so trust it over where
                    # their stories happen to appear (PA copy runs in The
                    # Independent, Reach copy across its papers). Only hold back
                    # when it may be a different person: a local or regional
                    # outlet in another group, or an email you've verified.
                    plausible_same_person = (
                        ((cur["tier"] in ("national", "broadcast", "specialist") and cur["region"] == "UK")
                         or (cur["group_name"] and cur["group_name"] == tgt["group_name"]))
                        and not verified_elsewhere)
                    if recent and not plausible_same_person:
                        kept_namesake.append(f"{full}: Register says {r['sponsor']}, finder has recent "
                                             f"stories at {j['outlet']}")
                    else:
                        conn.execute("UPDATE journalists SET primary_outlet_id = ?, primary_region = ?, "
                                     "primary_tier = ? WHERE id = ?", (o["id"], o["region"], o["tier"], jid))
                        moved.append(f"{full}: {j['outlet']} -> {outlet}")
                elif j["outlet"] != outlet and j["outlet"] == "ITV News (National)" and outlet.startswith("ITV News "):
                    # National ITV bucket -> the specific region the Register names
                    conn.execute("UPDATE journalists SET primary_outlet_id = ?, primary_region = ?, "
                                 "primary_tier = ? WHERE id = ?", (o["id"], o["region"], o["tier"], jid))
                    moved.append(f"{full}: {j['outlet']} -> {outlet}")

            conn.execute("INSERT OR REPLACE INTO journalist_specialisms (journalist_id, specialism, score) "
                         "VALUES (?, ?, 100)", (jid, LOBBY_TAG))
            tagged += 1
            seen.add(key)
            conn.execute("""
                INSERT INTO lobby_register (name_normalised, full_name, sponsor, outlet, other_occupation,
                    first_edition, last_edition, status, left_edition)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'current', NULL)
                ON CONFLICT(name_normalised) DO UPDATE SET
                    full_name = excluded.full_name, sponsor = excluded.sponsor, outlet = excluded.outlet,
                    other_occupation = excluded.other_occupation, last_edition = excluded.last_edition,
                    status = 'current', left_edition = NULL
            """, (key, full, r["sponsor"], outlet, r["other"], edition, edition))

        # Anyone tagged as lobby but not on this edition has left the list
        left = []
        for t in conn.execute("""
            SELECT j.id, j.full_name, j.name_normalised FROM journalist_specialisms s
            JOIN journalists j ON j.id = s.journalist_id
            WHERE s.specialism = ? AND s.score >= 100
        """, (LOBBY_TAG,)).fetchall():
            if t["name_normalised"] not in seen:
                conn.execute("DELETE FROM journalist_specialisms WHERE journalist_id = ? AND specialism = ?",
                             (t["id"], LOBBY_TAG))
                conn.execute("""
                    INSERT INTO lobby_register (name_normalised, full_name, status, left_edition, first_edition)
                    VALUES (?, ?, 'left', ?, ?)
                    ON CONFLICT(name_normalised) DO UPDATE SET status = 'left', left_edition = excluded.left_edition
                """, (t["name_normalised"], t["full_name"], edition, prev or "2026-04-20"))
                left.append(t["full_name"])
        conn.execute("INSERT OR REPLACE INTO lobby_editions (edition, entries) VALUES (?, ?)", (edition, len(rows)))

    print(f"\nTagged as lobby: {tagged}")
    print(f"Added to the finder: {len(added)}")
    for a in added:
        print(f"  + {a}")
    print(f"\nMoved to a new outlet: {len(moved)}")
    for m in moved:
        print(f"  > {m}")
    print(f"\nLeft the list (tag removed, still in the finder): {len(left)}")
    for name in left:
        print(f"  - {name}")
    if kept_namesake:
        print(f"\nNot moved, check by hand: {len(kept_namesake)}")
        for k in kept_namesake:
            print(f"  ? {k}")
    if new_outlets:
        print(f"\nNew outlets created: {', '.join(sorted(new_outlets))}")


if __name__ == "__main__":
    main()
