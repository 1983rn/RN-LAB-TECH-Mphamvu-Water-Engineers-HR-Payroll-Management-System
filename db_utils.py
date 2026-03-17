from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def init_db():
    """Initialize the database with all tables"""
    db.create_all()
    print("Database initialized successfully!")

def get_reference_number(prefix):
    """Generate unique reference numbers"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}{timestamp}"
