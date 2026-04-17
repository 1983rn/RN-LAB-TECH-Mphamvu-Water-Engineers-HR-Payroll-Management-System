import sqlite3
import os

def check_db():
    db_path = 'instance/system.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Tables in database:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(f" - {table[0]}")
        
    if ('payroll_batches',) in tables:
        print("\nTable 'payroll_batches' exists. Schema:")
        cursor.execute("PRAGMA table_info(payroll_batches);")
        for col in cursor.fetchall():
            print(f"   {col}")
    else:
        print("\nTable 'payroll_batches' DOES NOT exist.")
        
    conn.close()

if __name__ == '__main__':
    check_db()
