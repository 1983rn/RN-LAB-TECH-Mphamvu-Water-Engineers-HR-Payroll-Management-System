"""
Migration: Add 'department' column to rfq_responses table.

Safe to run multiple times (idempotent).
Backfills existing rows with 'Borehole Drilling'.
"""
import sqlite3
import os
import sys

# Locate the database file relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'system.db')

# Fall back to system.db in root if instance/ version not found
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, 'system.db')

if not os.path.exists(DB_PATH):
    print(f"ERROR: Could not find database at {DB_PATH}")
    sys.exit(1)

print(f"Using database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

try:
    # Check if column already exists
    cur.execute("PRAGMA table_info(rfq_responses)")
    columns = [row[1] for row in cur.fetchall()]

    if 'department' in columns:
        print("Column 'department' already exists in rfq_responses. Nothing to do.")
    else:
        print("Adding 'department' column to rfq_responses...")
        cur.execute(
            "ALTER TABLE rfq_responses ADD COLUMN department TEXT NOT NULL DEFAULT 'Borehole Drilling'"
        )
        conn.commit()
        print("Column added successfully.")

    # Verify and report
    cur.execute("SELECT COUNT(*) FROM rfq_responses")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rfq_responses WHERE department IS NULL OR department = ''")
    blank = cur.fetchone()[0]

    if blank > 0:
        print(f"Backfilling {blank} rows with department='Borehole Drilling'...")
        cur.execute(
            "UPDATE rfq_responses SET department = 'Borehole Drilling' WHERE department IS NULL OR department = ''"
        )
        conn.commit()
        print("Backfill complete.")

    print(f"\nDone. rfq_responses table has {total} row(s), all with a department value.")

except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    conn.close()
