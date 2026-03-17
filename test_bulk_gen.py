import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Employee
from utils.pdf_utils import generate_bulk_id_cards

def test_bulk_generation():
    with app.app_context():
        # Get all employees
        employees = Employee.query.all()
        
        if not employees:
            print("ERROR: No employees found in the database. Cannot test bulk generation.")
            return
            
        print(f"Testing bulk ID card generation for {len(employees)} employees...")
        
        try:
            # Generate the PDF
            pdf_buffer = generate_bulk_id_cards(employees)
            
            # Check if buffer has content
            size = pdf_buffer.getbuffer().nbytes
            print(f"SUCCESS: Generated PDF buffer of size {size} bytes.")
            
            if size > 1000:
                print("PDF generation looks correct (size > 1KB).")
            else:
                print("WARNING: PDF buffer seems suspiciously small.")
                
            # Optional: save to file for manual inspection if needed
            test_output = "test_bulk_output.pdf"
            with open(test_output, "wb") as f:
                f.write(pdf_buffer.getvalue())
            print(f"Saved test output to {test_output}")
            
        except Exception as e:
            print(f"ERROR generating PDF: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_bulk_generation()
