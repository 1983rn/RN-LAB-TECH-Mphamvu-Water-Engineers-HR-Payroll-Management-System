from app import app
from models import db

def create_table():
    with app.app_context():
        # This will only create missing tables
        db.create_all()
        print("Database tables verified/created successfully.")

if __name__ == "__main__":
    create_table()
