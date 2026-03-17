import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Employee
from utils.pdf_utils import generate_dual_sided_id_card

def test_id_generation():
    with app.app_context():
        # Get an employee to test with
        employee = Employee.query.first()
        
        if not employee:
            print("ERROR: No employees found in the database. Cannot test.")
            return
            
        print(f"Testing ID card generation for: {employee.first_name} {employee.last_name}")
        
        try:
            # Generate the PDF
            pdf_buffer = generate_dual_sided_id_card(employee)
            
            # Check if buffer has content
            size = pdf_buffer.getbuffer().nbytes
            print(f"SUCCESS: Generated PDF buffer of size {size} bytes.")
            
            if size > 1000:
                print("PDF generation looks correct (size > 1KB).")
            else:
                print("WARNING: PDF buffer seems suspiciously small.")
                
            # Optional: save to file for manual inspection if needed
            test_output = "test_id_output.pdf"
            with open(test_output, "wb") as f:
                f.write(pdf_buffer.getvalue())
            print(f"Saved test output to {test_output}")
            
        except Exception as e:
            print(f"ERROR generating PDF: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_id_generation()
