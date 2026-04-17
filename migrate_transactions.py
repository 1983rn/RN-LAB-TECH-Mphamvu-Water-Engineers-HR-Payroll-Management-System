import os
import sys

# Add the project root to the path so we can import models
sys.path.append(os.getcwd())

from app import app
from models import db, Transaction, Invoice

def migrate_transactions():
    with app.app_context():
        print("Starting transaction migration...")
        
        # Get all transactions
        transactions = Transaction.query.all()
        count = 0
        
        for tx in transactions:
            # If tx is linked to an invoice, use invoice department
            if tx.invoice:
                tx.department = tx.invoice.department
            else:
                # Default to Borehole Drilling as per user instructions
                tx.department = 'Borehole Drilling'
            
            count += 1
            
        db.session.commit()
        print(f"Successfully migrated {count} transactions.")

if __name__ == "__main__":
    migrate_transactions()
