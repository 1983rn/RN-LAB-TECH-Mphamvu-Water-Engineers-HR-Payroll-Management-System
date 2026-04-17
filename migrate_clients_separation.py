import sqlite3
import os

def migrate():
    db_path = 'instance/system.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(clients)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'department' not in columns:
            print("Adding 'department' column to clients table...")
            # We add it as nullable first, then set values, then we could enforce NOT NULL if we wanted
            # but for SQLite simplicity we will just add it with a default.
            cursor.execute("ALTER TABLE clients ADD COLUMN department VARCHAR(100) DEFAULT 'Borehole Drilling' NOT NULL")
            print("Migration successful.")
        else:
            print("Column 'department' already exists in clients.")
            
        conn.commit()
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
