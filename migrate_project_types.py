import sqlite3
import os

# FOUND table in: instance/system.db
db_path = 'instance/system.db'

def migrate():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(custom_project_types)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'department' not in columns:
            print("Adding 'department' column to instance/system.db...")
            cursor.execute("ALTER TABLE custom_project_types ADD COLUMN department VARCHAR(100) DEFAULT 'Borehole'")
            conn.commit()
            print("Successfully added 'department' column to 'custom_project_types' in instance/system.db.")
        else:
            print("Column 'department' already exists in instance/system.db.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    migrate()
