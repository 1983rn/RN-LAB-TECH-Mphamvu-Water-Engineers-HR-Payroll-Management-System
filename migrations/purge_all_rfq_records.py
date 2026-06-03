"""
One-time migration: Purge ALL legacy RFQ records from the database.

All 4 remaining records (IDs 3, 5, 6, 8) have been manually verified as
test/development data — not real client RFQs:
  - ID 3: Empty company name, generic "Geophysical survey" rows
  - ID 5: "MPHAMVU WATER ENGINEERS" (company testing with own name)
  - ID 6: "Mphamvu Water Engineers" (same)
  - ID 8: "Mphamvu Water Engineers" (same)

After this script runs, the rfq_responses table will be empty.
New RFQ records will only be created when a real user submits one via the UI.

Safe to run multiple times (idempotent).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, RFQResponse


def purge_all_rfq_records():
    """Delete every record in the rfq_responses table."""
    with app.app_context():
        count = RFQResponse.query.count()
        if count == 0:
            print("rfq_responses table is already empty. Nothing to do.")
            return

        print(f"Found {count} RFQ record(s). Purging all...")
        for rfq in RFQResponse.query.all():
            print(f"  Deleting RFQ ID={rfq.id}  company='{rfq.company}'")
            db.session.delete(rfq)

        db.session.commit()
        remaining = RFQResponse.query.count()
        print(f"\nPurge complete. Remaining records: {remaining}")


if __name__ == '__main__':
    purge_all_rfq_records()
