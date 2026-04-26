from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def init_db():
    """Initialize the database with all tables"""
    db.create_all()
    
    # Check for missing 'secret_code' column in page_authorizations (Manual Migration)
    try:
        from sqlalchemy import text
        # Using a raw connection to execute ALTER TABLE for SQLite
        with db.engine.connect() as conn:
            # We wrap in a try-except because ALTER TABLE will fail if the column already exists
            try:
                conn.execute(text("ALTER TABLE page_authorizations ADD COLUMN secret_code VARCHAR(4)"))
                conn.commit()
            except Exception:
                pass
                
            # Add payment columns to employees
            for col, dtype in [('bank_name', 'VARCHAR(100)'), ('account_number', 'VARCHAR(50)'), 
                               ('airtel_number', 'VARCHAR(20)'), ('tnm_mpamba_number', 'VARCHAR(20)')]:
                try:
                    conn.execute(text(f"ALTER TABLE employees ADD COLUMN {col} {dtype}"))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"Migration check skipped or failed: {e}")
        
    print("Database initialized successfully!")

def get_reference_number(prefix):
    """Generate unique reference numbers"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}{timestamp}"
