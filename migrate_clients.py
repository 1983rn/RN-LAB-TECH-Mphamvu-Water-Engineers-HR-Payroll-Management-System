import sqlite3

def migrate():
    print("Starting client table migration...")
    conn = sqlite3.connect('instance/system.db')
    c = conn.cursor()
    columns = [
        "total_transactions INTEGER DEFAULT 0",
        "completed_transactions INTEGER DEFAULT 0",
        "on_time_payments INTEGER DEFAULT 0",
        "defaults INTEGER DEFAULT 0",
        "credit_score INTEGER DEFAULT 0"
    ]
    
    for col in columns:
        try:
            c.execute(f"ALTER TABLE clients ADD COLUMN {col}")
            print(f"Added {col}")
        except sqlite3.OperationalError as e:
            print(f"Column already exists or error: {e}")
            
    conn.commit()
    conn.close()
    print("Migration finished.")

if __name__ == "__main__":
    migrate()
