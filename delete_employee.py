from app import app
from models import db, Employee, Payroll, Attendance

# Employment number to delete
employment_number = 'MWE/2016/0001'

with app.app_context():
    employee = Employee.query.filter_by(employment_number=employment_number).first()
    
    if employee:
        print(f"Deleting employee: {employee.first_name} {employee.last_name} ({employment_number})")
        
        # Delete related records first
        Payroll.query.filter_by(employee_id=employee.employee_id).delete()
        Attendance.query.filter_by(employee_id=employee.employee_id).delete()
        
        # Delete the employee
        db.session.delete(employee)
        db.session.commit()
        
        print(f"Successfully deleted employee and all related records")
    else:
        print(f"Employee not found: {employment_number}")
