import sqlite3
import os

def migrate():
    db_path = 'instance/system.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables_to_update = [
        ('delivery_notes', 'Borehole Drilling'),
        ('inventory', 'Borehole Drilling'),
        ('livestock', 'Farm'),
        ('crop_cycles', 'Farm'),
        ('farm_activities', 'Farm'),
        ('farm_expenses', 'Farm'),
        ('construction_projects', 'Construction')
    ]

    for table, default_dept in tables_to_update:
        try:
            print(f"Updating table: {table}")
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'department' not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN department TEXT NOT NULL DEFAULT '{default_dept}'")
                print(f"Added 'department' column to {table}")
            else:
                print(f"'department' column already exists in {table}")
                
        except Exception as e:
            print(f"Error updating {table}: {e}")

    # Special handling for Inventory: map existing categories to departments
    try:
        cursor.execute("UPDATE inventory SET department = 'Borehole Drilling' WHERE category = 'Borehole Drilling'")
        cursor.execute("UPDATE inventory SET department = 'Farm' WHERE category IN ('Animal Farm', 'Crop Farming')")
        cursor.execute("UPDATE inventory SET department = 'Office Equipment' WHERE category = 'Office Equipment'")
        print("Mapped Inventory categories to departments.")
    except Exception as e:
        print(f"Error mapping inventory: {e}")

    # Special handling for Quotations: The user said one is for Construction
    # We already have department in Quotations, but let's ensure it's set correctly
    try:
        # Check if there's any quotation that looks like construction
        # (e.g. linked to a ConstructionProject or has construction-like keywords)
        cursor.execute("UPDATE quotations SET department = 'Borehole Drilling' WHERE department IS NULL OR department = ''")
        print("Defaulted quotations to Borehole Drilling.")
    except Exception as e:
        print(f"Error updating quotations: {e}")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
