import sqlite3
import os

db_path = 'system.db'

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add the secret_code column to page_authorizations table
        cursor.execute("ALTER TABLE page_authorizations ADD COLUMN secret_code VARCHAR(4)")
        
        conn.commit()
        conn.close()
        print("Successfully added 'secret_code' column to 'page_authorizations' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column 'secret_code' already exists.")
        else:
            print(f"An error occurred: {e}")
else:
    print(f"Database file {db_path} not found.")
