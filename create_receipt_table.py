from app import app
from db_utils import db
from models import GeneralReceipt

with app.app_context():
    # Only create the new table
    GeneralReceipt.__table__.create(db.engine, checkfirst=True)
    print("GeneralReceipt table created successfully!")
