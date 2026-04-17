import sqlite3
import os

def alter_db():
    db_path = 'instance/system.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables_to_update = ['quotations', 'contracts', 'invoices']
    
    for table in tables_to_update:
        try:
            # Check if column already exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'department' not in columns:
                print(f"Adding 'department' column to {table}...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN department VARCHAR(100) DEFAULT 'Borehole Drilling' NOT NULL")
            else:
                print(f"Column 'department' already exists in {table}.")
        except Exception as e:
            print(f"Error updating {table}: {e}")
            
    conn.commit()
    conn.close()
    print("Database schema update completed.")

if __name__ == '__main__':
    alter_db()
