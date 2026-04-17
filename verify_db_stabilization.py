from app import app, db
from models import PayrollBatch, PayrollOTP

def verify():
    print("Initializing application context...")
    with app.app_context():
        try:
            print("Checking PayrollBatch table...")
            count = PayrollBatch.query.count()
            print(f"Connection successful. PayrollBatch count: {count}")
            
            print("Checking PayrollOTP table...")
            otp_count = PayrollOTP.query.count()
            print(f"Connection successful. PayrollOTP count: {otp_count}")
            
            print("\nDatabase verification COMPLETE. System is stable.")
        except Exception as e:
            print(f"\nVerification FAILED: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    verify()
