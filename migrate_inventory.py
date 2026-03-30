import sqlite3
import os

def migrate():
    db_path = 'd:/2025-2026/PRODUCTION/USA/RN-LAB-TECH-HR Payroll Management System/instance/system.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(inventory)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'subcategory' not in columns:
            cursor.execute("ALTER TABLE inventory ADD COLUMN subcategory VARCHAR(100)")
            cursor.execute("UPDATE inventory SET subcategory = 'General'")
            print("Added 'subcategory' column")
            
        if 'condition' not in columns:
            cursor.execute("ALTER TABLE inventory ADD COLUMN condition VARCHAR(100)")
            cursor.execute("UPDATE inventory SET condition = 'New/Excellent/Good'")
            print("Added 'condition' column")
            
        if 'location' not in columns:
            cursor.execute("ALTER TABLE inventory ADD COLUMN location VARCHAR(200)")
            cursor.execute("UPDATE inventory SET location = 'Main Office'")
            print("Added 'location' column")
            
        conn.commit()
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
