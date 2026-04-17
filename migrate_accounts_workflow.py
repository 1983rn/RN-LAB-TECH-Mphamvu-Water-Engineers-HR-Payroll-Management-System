from app import app, db
from models import PayrollBatch, PayrollOTP

def migrate():
    with app.app_context():
        print("Starting Accounts & Payroll Workflow database migration...")
        try:
            db.create_all()
            print("Successfully created new tables: payroll_batches, payroll_otps")
        except Exception as e:
            print(f"Error during migration: {str(e)}")

if __name__ == '__main__':
    migrate()
