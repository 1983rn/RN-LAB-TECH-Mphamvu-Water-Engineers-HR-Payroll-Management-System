import sqlite3
import os

db_path = 'instance/system.db'

def clear_farm_types():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Show existing Farm project types
    cursor.execute("SELECT id, project_type, department FROM custom_project_types WHERE department = 'Farm'")
    rows = cursor.fetchall()
    
    if not rows:
        print("No Farm project types found in database.")
    else:
        print(f"Found {len(rows)} Farm project types:")
        for row in rows:
            print(f"  ID={row[0]}: {row[1]} (dept={row[2]})")
        
        # Delete them
        cursor.execute("DELETE FROM custom_project_types WHERE department = 'Farm'")
        conn.commit()
        print(f"\nDeleted {len(rows)} Farm project types from database.")
    
    conn.close()

if __name__ == "__main__":
    clear_farm_types()
