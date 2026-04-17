from app import app
from models import db, Quotation, Invoice, Contract

def migrate():
    with app.app_context():
        # Update existing records
        quotations = Quotation.query.all()
        for q in quotations:
            if not q.department:
                q.department = 'Borehole Drilling'
        
        invoices = Invoice.query.all()
        for i in invoices:
            if not i.department:
                i.department = 'Borehole Drilling'
                
        contracts = Contract.query.all()
        for c in contracts:
            if not c.department:
                c.department = 'Borehole Drilling'
        
        db.session.commit()
        print("Migration completed: All existing Quotations, Invoices, and Contracts assigned to 'Borehole Drilling'.")

if __name__ == '__main__':
    migrate()
