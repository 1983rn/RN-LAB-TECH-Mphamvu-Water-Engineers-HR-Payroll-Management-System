import sqlite3
import os

def inspect():
    db_path = 'instance/system.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(invoices);")
    columns = cursor.fetchall()
    print("Columns in invoices table:")
    for col in columns:
        print(f" - Name: {col[1]}, Type: {col[2]}, Nullable: {1 if col[3] == 0 else 0}")
        
    conn.close()

if __name__ == '__main__':
    inspect()
