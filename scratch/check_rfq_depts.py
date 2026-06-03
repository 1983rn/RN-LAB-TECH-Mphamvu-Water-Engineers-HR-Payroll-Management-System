import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, RFQResponse, RFQRequest

with app.app_context():
    responses = RFQResponse.query.all()
    print("--- RFQ Responses ---")
    for r in responses:
        print(f"ID: {r.id}, Company: {r.company}, Dept: {r.department}, Created: {r.created_at}")

    requests = RFQRequest.query.all()
    print("\n--- RFQ Requests ---")
    for req in requests:
        print(f"ID: {req.id}, Client: {req.client}, Item: {req.item}, Status: {req.status}, Created: {req.created_at}")
