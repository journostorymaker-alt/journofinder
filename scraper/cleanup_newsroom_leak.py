"""
One-off cleanup: find journalists whose primary email is a newsroom address
(newsdesk@, news@, editor@, etc.) and either:
  - if the email isn't already a newsroom_contact for that outlet, add it
  - either way, remove the bad email from the journalist record

This fixes the pre-upgrade Hackney Citizen bug where 7 different journalists
all had newsdesk@hackneycitizen.co.uk as their email. After today's scraper
upgrade, this bug doesn't recur for new data, but old data still has the
wrong attributions.

Usage: python scraper/cleanup_newsroom_leak.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_conn

# Patterns that indicate a newsroom/role email rather than a personal one
NEWSROOM_LOCAL_PARTS = {
    "newsdesk", "news", "tips", "tipoff", "tip-off",
    "editor", "editorial", "edit",
    "planning", "diary",
    "letters", "comment", "comments",
    "press", "info", "hello", "contact", "admin",
    "environment", "environmentdesk",
    "business", "businessdesk",
    "politics", "politicsdesk",
    "sport", "sportsdesk",
}

# Map newsroom local-parts to role categories
ROLE_MAP = {
    "newsdesk": "newsdesk", "news": "newsdesk", "tips": "tips",
    "tipoff": "tips", "tip-off": "tips",
    "editor": "editor", "editorial": "editor", "edit": "editor",
    "planning": "planning", "diary": "planning",
    "environment": "environment_desk", "environmentdesk": "environment_desk",
    "business": "business_desk", "businessdesk": "business_desk",
    "politics": "politics_desk", "politicsdesk": "politics_desk",
    "sport": "sport_desk", "sportsdesk": "sport_desk",
    "letters": "letters", "comment": "comment", "comments": "comment",
    "press": "press",
}


def is_newsroom_email(email):
    """True if an email's local-part is a known newsroom prefix.
    
    Matches exact local-parts only — does NOT strip dots/hyphens, because
    'first.last' patterns like 's.port' (S. Port) would falsely match
    the 'sport' newsroom term.
    """
    if not email or "@" not in email:
        return False
    local = email.split("@")[0].lower().strip()
    return local in NEWSROOM_LOCAL_PARTS


def classify_role(email):
    if not email or "@" not in email:
        return None
    local = email.split("@")[0].lower().strip()
    return ROLE_MAP.get(local)


def main():
    print("Scanning journalist_emails for newsroom-pattern addresses...")
    
    with get_conn() as conn:
        # Find every journalist email that looks like a newsroom address
        bad_emails = []
        for r in conn.execute("""
            SELECT je.id, je.journalist_id, je.email, je.is_primary,
                   j.full_name, j.primary_outlet_id, o.name as outlet_name
            FROM journalist_emails je
            JOIN journalists j ON je.journalist_id = j.id
            JOIN outlets o ON j.primary_outlet_id = o.id
        """):
            if is_newsroom_email(r["email"]):
                bad_emails.append(dict(r))
        
        print(f"Found {len(bad_emails)} newsroom-pattern emails wrongly attached to journalists")
        
        if not bad_emails:
            print("Nothing to clean up.")
            return
        
        # Group by outlet+email so we move each unique address only once
        by_outlet_email = {}
        for be in bad_emails:
            key = (be["primary_outlet_id"], be["email"])
            if key not in by_outlet_email:
                by_outlet_email[key] = []
            by_outlet_email[key].append(be)
        
        print(f"\nUnique newsroom addresses across {len(by_outlet_email)} outlet/email pairs:")
        for (outlet_id, email), affected in sorted(by_outlet_email.items(),
                                                    key=lambda x: -len(x[1])):
            outlet_name = affected[0]["outlet_name"]
            print(f"  {len(affected):3} × {email}  ({outlet_name})")
        
        print("\nMigrating these to newsroom_contacts table and removing from journalists...")
        
        moved = 0
        deleted = 0
        
        for (outlet_id, email), affected in by_outlet_email.items():
            # Add to newsroom_contacts if not already there
            existing = conn.execute(
                "SELECT id FROM newsroom_contacts WHERE outlet_id = ? AND email = ?",
                (outlet_id, email)
            ).fetchone()
            
            if not existing:
                role = classify_role(email) or "newsdesk"
                conn.execute("""
                    INSERT INTO newsroom_contacts (outlet_id, role, email, confidence, source)
                    VALUES (?, ?, ?, 'verified', 'cleanup_migration')
                """, (outlet_id, role, email))
                moved += 1
            
            # Delete the bad email rows from journalist_emails
            for be in affected:
                conn.execute("DELETE FROM journalist_emails WHERE id = ?", (be["id"],))
                deleted += 1
        
        # Where the deletion left a journalist with no primary email, promote
        # any remaining email to primary
        conn.execute("""
            UPDATE journalist_emails
            SET is_primary = 1
            WHERE id IN (
                SELECT MIN(je.id)
                FROM journalist_emails je
                LEFT JOIN journalist_emails je_primary
                  ON je_primary.journalist_id = je.journalist_id
                  AND je_primary.is_primary = 1
                WHERE je_primary.id IS NULL
                GROUP BY je.journalist_id
            )
        """)
        
        # Some journalists may now have NO emails at all
        orphaned_journalists = conn.execute("""
            SELECT COUNT(DISTINCT j.id)
            FROM journalists j
            LEFT JOIN journalist_emails je ON je.journalist_id = j.id
            WHERE je.id IS NULL
        """).fetchone()[0]
        
        print(f"\nDone.")
        print(f"  Newsroom contacts added: {moved}")
        print(f"  Already-existing newsroom contacts (skipped): {len(by_outlet_email) - moved}")
        print(f"  Journalist email rows deleted: {deleted}")
        print(f"  Journalists now with no email: {orphaned_journalists}")
        
        # Final check
        remaining = conn.execute("""
            SELECT COUNT(*) FROM journalist_emails WHERE
                email LIKE 'newsdesk@%' OR
                email LIKE 'news@%' OR
                email LIKE 'editor@%' OR
                email LIKE 'tips@%' OR
                email LIKE 'letters@%' OR
                email LIKE 'press@%'
        """).fetchone()[0]
        print(f"  Newsroom-pattern emails still in journalist_emails: {remaining}")


if __name__ == "__main__":
    main()
