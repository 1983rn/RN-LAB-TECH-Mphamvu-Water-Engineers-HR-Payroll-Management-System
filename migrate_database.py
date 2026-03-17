from app import app
from models import db
from sqlalchemy import text

with app.app_context():
    try:
        # Check if column exists
        result = db.session.execute(text("PRAGMA table_info(employees)"))
        columns = [row[1] for row in result]
        
        if 'date_dismissed' not in columns:
            print("Adding date_dismissed column to employees table...")
            db.session.execute(text("ALTER TABLE employees ADD COLUMN date_dismissed DATE"))
            db.session.commit()
            print("Successfully added date_dismissed column")
        else:
            print("date_dismissed column already exists")
            
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        db.session.rollback()
