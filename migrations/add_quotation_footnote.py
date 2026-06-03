"""
Migration script to add footnote column to quotations table
"""
import sqlite3
import os

def add_footnote_column():
    """Add footnote column to quotations table"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'system.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if footnote column already exists
        cursor.execute("PRAGMA table_info(quotations)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'footnote' not in columns:
            # Add footnote column
            cursor.execute("ALTER TABLE quotations ADD COLUMN footnote TEXT")
            print("Successfully added footnote column to quotations table")
        else:
            print("Footnote column already exists in quotations table")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error adding footnote column: {e}")
        return False

if __name__ == "__main__":
    add_footnote_column()
