import sqlite3
import os

db_path = os.path.join('instance', 'system.db')

def apply_schema():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Applying Farm Schema updates...")
    
    # 1. New Tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS livestock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        animal_type VARCHAR(100) NOT NULL,
        tag_number VARCHAR(50) UNIQUE,
        gender VARCHAR(20),
        breed VARCHAR(100),
        birth_date DATE,
        death_date DATE,
        purchase_price FLOAT DEFAULT 0.0,
        status VARCHAR(50) DEFAULT 'Alive',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS crop_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crop_name VARCHAR(100) NOT NULL,
        variety VARCHAR(100),
        planting_date DATE,
        expected_harvest_date DATE,
        actual_harvest_date DATE,
        quantity_harvested FLOAT DEFAULT 0.0,
        unit VARCHAR(50) DEFAULT 'Bags',
        status VARCHAR(50) DEFAULT 'Growing',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 2. Add Columns to existing tables
    # Helper to add column if it doesn't exist
    def add_column_if_missing(table, column, type_def):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
            print(f"Added column {column} to {table}")
        except sqlite3.OperationalError:
            print(f"Column {column} already exists in {table} (or table doesn't exist)")

    add_column_if_missing('farm_inputs', 'unit_price', 'FLOAT DEFAULT 0.0')
    add_column_if_missing('farm_inputs', 'total_cost', 'FLOAT DEFAULT 0.0')
    add_column_if_missing('farm_inputs', 'department', "VARCHAR(100) DEFAULT 'Farm'")
    add_column_if_missing('farm_outputs', 'department', "VARCHAR(100) DEFAULT 'Farm'")
    
    # Handle NULL constraints if needed (SQLite doesn't support MODIFY COLUMN)
    # We will just rely on the fact that existing rows have values, and new rows can be handled by nullable=True in SQLAlchemy.
    # Note: SQLite ALTER TABLE ADD COLUMN always adds as NULLABLE unless a DEFAULT is provided.
    
    conn.commit()
    conn.close()
    print("Farm Schema updates applied successfully.")

if __name__ == "__main__":
    apply_schema()
