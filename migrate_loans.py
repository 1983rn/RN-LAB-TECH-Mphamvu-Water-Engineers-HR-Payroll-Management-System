import sqlite3
import os

def migrate_loans():
    db_path = "instance/system.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Drop old table to ensure clean start with new schema
        cursor.execute("DROP TABLE IF EXISTS employee_loans")
        
        # Create new table based on directive
        cursor.execute("""
        CREATE TABLE employee_loans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            employment_no TEXT,
            loan_amount REAL,
            repayment_months INTEGER,
            monthly_deduction REAL,
            amount_paid REAL,
            balance REAL,
            start_date TEXT,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
        )
        """)
        
        # Also need to add absentee_deduction to payroll if not exists (redundancy check)
        cursor.execute("PRAGMA table_info(payroll)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'absentee_deduction' not in columns:
            cursor.execute("ALTER TABLE payroll ADD COLUMN absentee_deduction REAL DEFAULT 0")
            
        conn.commit()
        print("Database migration for Loans and Payroll complete.")
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_loans()
