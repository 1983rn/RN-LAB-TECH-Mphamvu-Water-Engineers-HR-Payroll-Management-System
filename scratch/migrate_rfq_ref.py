import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'water_engineers.db')
if not os.path.exists(db_path):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'water_engineers.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE rfq_responses ADD COLUMN reference_number VARCHAR(50)")
    print("Added reference_number to rfq_responses")
except Exception as e:
    print("Migration error (may already exist):", e)

try:
    cursor.execute("CREATE UNIQUE INDEX ix_rfq_responses_reference_number ON rfq_responses(reference_number)")
    print("Created index on reference_number")
except Exception as e:
    print("Index error (may already exist):", e)

conn.commit()
conn.close()
