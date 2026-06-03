import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE rfq_responses ADD COLUMN reference_number VARCHAR(50)"))
        db.session.commit()
        print("Added reference_number to rfq_responses")
    except Exception as e:
        print("Migration error:", e)

    try:
        db.session.execute(text("CREATE UNIQUE INDEX ix_rfq_responses_reference_number ON rfq_responses(reference_number)"))
        db.session.commit()
        print("Created index on reference_number")
    except Exception as e:
        print("Index error:", e)
