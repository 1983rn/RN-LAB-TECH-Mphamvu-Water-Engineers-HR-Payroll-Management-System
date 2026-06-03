import os
from app import app
from models import db
from sqlalchemy import text

def migrate():
    print("Starting database migration...")
    with app.app_context():
        # Get engine
        engine = db.engine
        
        # Check connection type
        dialect = engine.url.get_dialect().name
        print(f"Database dialect detected: {dialect}")
        
        # Add column
        try:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN project_name VARCHAR(255)"))
                print("Column 'project_name' successfully added to 'invoices' table.")
        except Exception as e:
            err_msg = str(e).lower()
            if "duplicate column" in err_msg or "already exists" in err_msg:
                print("Column 'project_name' already exists in 'invoices' table.")
            else:
                print(f"Error migrating database: {e}")

if __name__ == '__main__':
    migrate()
