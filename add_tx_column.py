import sqlite3
import os

db_path = os.path.join('instance', 'system.db')

def add_column():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"Adding 'department' column to 'transactions' table in {db_path}...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN department VARCHAR(100) DEFAULT 'Borehole Drilling'")
        
        conn.commit()
        conn.close()
        print("Column added successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_column()
