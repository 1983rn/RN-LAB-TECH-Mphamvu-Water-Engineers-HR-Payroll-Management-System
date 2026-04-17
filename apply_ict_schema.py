import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db

def apply_schema():
    print("Applying ICT schema...")
    with app.app_context():
        # This will create new tables (like ict_projects, ict_tasks, ict_developers, ict_trainings)
        # It will NOT drop existing tables
        db.create_all()
        print("Schema applied successfully!")

if __name__ == "__main__":
    apply_schema()
