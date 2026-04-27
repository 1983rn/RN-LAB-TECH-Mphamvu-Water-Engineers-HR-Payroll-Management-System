import sys
import os

# Add the current directory to sys.path to import app and models
sys.path.append(os.getcwd())

from app import app
from db_utils import db
from models import Employee, Inventory, Client, Quotation, CashBookEntry, Contract, Invoice, Transaction

def migrate_lodge_name():
    with app.app_context():
        print("Starting Lodge rebranding migration...")
        
        # 1. Update Employees
        emp_count = Employee.query.filter(Employee.department.ilike('%Lodge / Rest House%')).update(
            {Employee.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {emp_count} employees.")
        
        # 2. Update Inventory
        inv_count = Inventory.query.filter(Inventory.department.ilike('%Lodge / Rest House%')).update(
            {Inventory.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {inv_count} inventory items.")
        
        # 3. Update Clients
        cli_count = Client.query.filter(Client.department.ilike('%Lodge / Rest House%')).update(
            {Client.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {cli_count} clients.")
        
        # 4. Update Quotations
        quo_count = Quotation.query.filter(Quotation.department.ilike('%Lodge / Rest House%')).update(
            {Quotation.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {quo_count} quotations.")
        
        # 5. Update CashBookEntry
        cash_count = CashBookEntry.query.filter(CashBookEntry.department.ilike('%Lodge / Rest House%')).update(
            {CashBookEntry.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {cash_count} cashbook entries.")

        # 6. Update Invoices
        inv_count2 = Invoice.query.filter(Invoice.department.ilike('%Lodge / Rest House%')).update(
            {Invoice.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {inv_count2} invoices.")

        # 7. Update Transactions
        trx_count = Transaction.query.filter(Transaction.department.ilike('%Lodge / Rest House%')).update(
            {Transaction.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {trx_count} transactions.")

        # 8. Update Contracts
        con_count = Contract.query.filter(Contract.department.ilike('%Lodge / Rest House%')).update(
            {Contract.department: 'Lodge'}, synchronize_session=False
        )
        print(f"Updated {con_count} contracts.")
        
        db.session.commit()
        print("Lodge rebranding migration complete.")

if __name__ == "__main__":
    migrate_lodge_name()
