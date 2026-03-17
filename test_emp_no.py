import sys
import os
from datetime import datetime

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Employee
from employees.employee_routes import generate_employment_number

def test_generation():
    with app.app_context():
        # Test 1: Generate initial number (assuming year is 2026)
        year = datetime.now().year
        print("Testing generation logic...")
        
        # Get count to know what to expect
        prefix = f"MWE/{year}/"
        last_emp = Employee.query.filter(Employee.employment_number.like(f"{prefix}%"))\
                                 .order_by(Employee.employment_number.desc()).first()
        
        if last_emp:
            expected_num = int(last_emp.employment_number.split('/')[-1]) + 1
        else:
            expected_num = 1
            
        expected_str = f"MWE/{year}/{str(expected_num).zfill(4)}"
        
        generated = generate_employment_number()
        print(f"Generated: {generated}")
        print(f"Expected:  {expected_str}")
        
        if generated == expected_str:
            print("SUCCESS: sequence logic is correct.")
        else:
            print("ERROR: incorrect sequence logic.")
            
        # Test 2: Create a dummy employee and test generation again
        print("\nTesting database insertion logic...")
        try:
            dummy = Employee(
                employment_number=generated,
                first_name="Test",
                last_name="User",
                department="IT",
                position="Tester",
                salary=1000.0,
                date_hired=datetime.now().date(),
                phone="1234567890",
                email="test@example.com",
                address="Test Address"
            )
            db.session.add(dummy)
            db.session.commit()
            print(f"Inserted dummy employee with number: {generated}")
            
            # The next generated number should be incremented
            next_generated = generate_employment_number()
            expected_next = f"MWE/{year}/{str(expected_num + 1).zfill(4)}"
            
            print(f"Next generated: {next_generated}")
            print(f"Expected next:  {expected_next}")
            
            if next_generated == expected_next:
                print("SUCCESS: consecutive numbers are correct.")
            else:
                print("ERROR: consecutive numbering failed.")
                
            # Clean up
            db.session.delete(dummy)
            db.session.commit()
            print("\nCleaned up dummy employee.")
            
        except Exception as e:
            print(f"Database error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    test_generation()
