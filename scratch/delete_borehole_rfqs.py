import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, RFQResponse

with app.app_context():
    responses = RFQResponse.query.filter_by(department='Borehole Drilling').all()
    for r in responses:
        db.session.delete(r)
    db.session.commit()
    print(f"Deleted {len(responses)} RFQ responses in Borehole Drilling department.")
