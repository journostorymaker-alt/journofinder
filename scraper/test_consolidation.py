"""Inject fake bylines to test the consolidation logic without network access."""
import sys
from db import init_db, sync_outlets, get_conn
from outlets import OUTLETS

def seed_test_data():
    init_db()
    sync_outlets(OUTLETS)
    
    with get_conn() as conn:
        # Wipe existing test data
        conn.execute("DELETE FROM journalist_specialisms")
        conn.execute("DELETE FROM journalist_emails")
        conn.execute("DELETE FROM bylines")
        conn.execute("DELETE FROM journalists")
        
        # Helper
        def get_outlet_id(name):
            return conn.execute("SELECT id FROM outlets WHERE name = ?", (name,)).fetchone()["id"]
        
        # Test case 1: A clear local staffer at Bristol Cable
        # Should classify as local_staff
        bristol_id = get_outlet_id("The Bristol Cable")
        cur = conn.execute("""
            INSERT INTO journalists (full_name, name_normalised, first_name, last_name, primary_outlet_id)
            VALUES ('Priyanka Raval', 'priyanka raval', 'Priyanka', 'Raval', ?)
        """, (bristol_id,))
        jid = cur.lastrowid
        for i in range(20):
            conn.execute("""
                INSERT INTO bylines (journalist_id, outlet_id, article_url, article_title, keywords)
                VALUES (?, ?, ?, ?, ?)
            """, (jid, bristol_id, f"https://thebristolcable.org/test-{i}", f"Bristol housing story {i}", "housing,investigation,local_government"))
        
        # Test case 2: A Reach plc network reporter — same byline across many regions
        # Should classify as network_reporter
        outlets_for_network = ["Manchester Evening News", "Liverpool Echo", "Birmingham Mail", 
                                "Bristol Post / BristolLive", "ChronicleLive (Newcastle)", "LeedsLive"]
        cur = conn.execute("""
            INSERT INTO journalists (full_name, name_normalised, first_name, last_name, primary_outlet_id)
            VALUES ('David Brown', 'david brown', 'David', 'Brown', ?)
        """, (get_outlet_id("Manchester Evening News"),))
        jid = cur.lastrowid
        for i, oname in enumerate(outlets_for_network):
            oid = get_outlet_id(oname)
            for j in range(3):
                conn.execute("""
                    INSERT INTO bylines (journalist_id, outlet_id, article_url, article_title, keywords)
                    VALUES (?, ?, ?, ?, ?)
                """, (jid, oid, f"https://example.com/network-{i}-{j}", f"UK news story {i}-{j}", "politics"))
        
        # Test case 3: Regional staff at Yorkshire titles
        yorkshire_outlets = ["Yorkshire Post", "Yorkshire Evening Post", "The Star (Sheffield)"]
        cur = conn.execute("""
            INSERT INTO journalists (full_name, name_normalised, first_name, last_name, primary_outlet_id)
            VALUES ('Sarah McGregor', 'sarah mcgregor', 'Sarah', 'McGregor', ?)
        """, (get_outlet_id("Yorkshire Post"),))
        jid = cur.lastrowid
        for oname in yorkshire_outlets:
            oid = get_outlet_id(oname)
            for j in range(8):
                conn.execute("""
                    INSERT INTO bylines (journalist_id, outlet_id, article_url, article_title, keywords)
                    VALUES (?, ?, ?, ?, ?)
                """, (jid, oid, f"https://example.com/yorks-{oname}-{j}", f"Yorkshire farming story {j}", "agriculture,environment"))
        
        # Test case 4: National journalist
        guardian_id = get_outlet_id("The Guardian")
        cur = conn.execute("""
            INSERT INTO journalists (full_name, name_normalised, first_name, last_name, primary_outlet_id)
            VALUES ('Helena Horton', 'helena horton', 'Helena', 'Horton', ?)
        """, (guardian_id,))
        jid = cur.lastrowid
        for i in range(15):
            conn.execute("""
                INSERT INTO bylines (journalist_id, outlet_id, article_url, article_title, keywords)
                VALUES (?, ?, ?, ?, ?)
            """, (jid, guardian_id, f"https://theguardian.com/test-{i}", f"Climate environment story {i}", "environment,investigation"))
        
        # Test case 5: Specialist environment journalist at Ferret
        ferret_id = get_outlet_id("The Ferret")
        cur = conn.execute("""
            INSERT INTO journalists (full_name, name_normalised, first_name, last_name, primary_outlet_id)
            VALUES ('Rob Edwards', 'rob edwards', 'Rob', 'Edwards', ?)
        """, (ferret_id,))
        jid = cur.lastrowid
        for i in range(12):
            conn.execute("""
                INSERT INTO bylines (journalist_id, outlet_id, article_url, article_title, keywords)
                VALUES (?, ?, ?, ?, ?)
            """, (jid, ferret_id, f"https://theferret.scot/test-{i}", f"Salmon farming pollution story {i}", "environment,fisheries,investigation"))

if __name__ == "__main__":
    seed_test_data()
    print("Test data seeded. Running consolidate...\n")
    
    from consolidate import consolidate
    consolidate()
    
    print("\n--- Sample journalist records ---")
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT j.full_name, o.name as outlet, j.classification, 
                   j.total_bylines, j.distinct_outlets, j.syndication_score,
                   j.primary_region
            FROM journalists j
            JOIN outlets o ON j.primary_outlet_id = o.id
        """).fetchall()
        for r in rows:
            print(f"  {r['full_name']:25} | {r['outlet']:30} | {r['classification']:20} | bylines={r['total_bylines']}, outlets={r['distinct_outlets']}, synd={r['syndication_score']}")
        
        print("\n--- Generated emails ---")
        rows = conn.execute("""
            SELECT j.full_name, e.email, e.confidence
            FROM journalist_emails e
            JOIN journalists j ON e.journalist_id = j.id
            ORDER BY j.full_name, e.is_primary DESC
        """).fetchall()
        for r in rows:
            print(f"  {r['full_name']:25} | {r['email']:50} | {r['confidence']}")
        
        print("\n--- Specialisms ---")
        rows = conn.execute("""
            SELECT j.full_name, GROUP_CONCAT(s.specialism || '(' || s.score || ')') as specs
            FROM journalist_specialisms s
            JOIN journalists j ON s.journalist_id = j.id
            GROUP BY j.id
        """).fetchall()
        for r in rows:
            print(f"  {r['full_name']:25} | {r['specs']}")
