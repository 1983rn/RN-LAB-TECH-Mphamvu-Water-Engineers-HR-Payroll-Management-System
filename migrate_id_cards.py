import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'system.db')
    
    # Try the root directory if instance dir is not used
    if not os.path.exists(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'system.db')
        
    print(f"Connecting to database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(employees)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'photo_path' not in columns:
            print("Adding 'photo_path' column to 'employees' table...")
            cursor.execute("ALTER TABLE employees ADD COLUMN photo_path TEXT")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column 'photo_path' already exists. No migration needed.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    migrate()
