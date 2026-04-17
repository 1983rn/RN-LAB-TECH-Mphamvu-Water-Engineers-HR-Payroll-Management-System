import sqlite3
import os

db_files = [
    'system.db',
    'database.db',
    'database/system.db',
    'instance/system.db',
    'database/payroll.db'
]

def check_tables():
    for db_path in db_files:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_project_types'")
                exists = cursor.fetchone()
                if exists:
                    print(f"FOUND table in: {db_path}")
                else:
                    print(f"Not in: {db_path}")
                conn.close()
            except Exception as e:
                print(f"Error checking {db_path}: {e}")
        else:
            print(f"File not found: {db_path}")

if __name__ == "__main__":
    check_tables()
