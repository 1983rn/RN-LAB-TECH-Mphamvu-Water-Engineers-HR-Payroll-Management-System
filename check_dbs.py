import sqlite3
import os

def check_dbs():
    dbs = ['database.db', 'system.db']
    for db_path in dbs:
        print(f"Checking {db_path}...")
        if not os.path.exists(db_path):
            print(f"  {db_path} not found.")
            continue
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            if tables:
                print(f"  Tables: {[t[0] for t in tables]}")
            else:
                print("  No tables found.")
            conn.close()
        except Exception as e:
            print(f"  Error checking {db_path}: {e}")

if __name__ == '__main__':
    check_dbs()
