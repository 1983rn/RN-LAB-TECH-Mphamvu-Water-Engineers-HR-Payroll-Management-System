from app import app
from db_utils import init_db

def finalize_db():
    print("Finalizing database initialization...")
    with app.app_context():
        try:
            init_db()
            print("Database initialized successfully.")
            
            from models import PayrollBatch
            count = PayrollBatch.query.count()
            print(f"Verified: PayrollBatch table is accessible. Count: {count}")
            
            print("\nDatabase Schema is now STABLE.")
        except Exception as e:
            print(f"Error during finalization: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    finalize_db()
