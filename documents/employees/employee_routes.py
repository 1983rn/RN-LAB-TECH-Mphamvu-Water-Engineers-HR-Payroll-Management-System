from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, Response
from werkzeug.utils import secure_filename
from models import db, Employee, Payroll, Attendance, DisciplinaryRecord
from datetime import datetime, date
import os
import uuid
import base64
from PIL import Image
from functools import wraps
from utils.photo_cleaner import clean_employee_photo

employee_bp = Blueprint('employees', __name__, url_prefix='/employees')

def generate_employment_number():
    year = datetime.now().year
    prefix = f"MWE/{year}/"
    
    # Extract just the sequence number part from the string
    # E.g. 'MWE/2026/0001' -> extract '0001'
    last_employee = Employee.query.filter(Employee.employment_number.like(f"{prefix}%"))\
                                  .order_by(Employee.employment_number.desc())\
                                  .first()
                                  
    if last_employee:
        try:
            last_number = int(last_employee.employment_number.split('/')[-1])
            new_number = last_number + 1
        except ValueError:
            new_number = 1
    else:
        new_number = 1
        
    return f"{prefix}{str(new_number).zfill(4)}"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def hr_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['Administrator', 'HR Manager']:
            flash('HR access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@employee_bp.route('/')
@login_required
@hr_required
def list_employees():
    # Filter out Deleted and Dismissed employees from the main directory
    employees = Employee.query.filter(~Employee.status.in_(['Deleted', 'Dismissed'])).all()
    return render_template('employees/list.html', employees=employees)

@employee_bp.route('/add', methods=['GET', 'POST'])
@login_required
@hr_required
def add_employee():
    if request.method == 'POST':
        try:
            employee = Employee(
                employment_number=generate_employment_number(),
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                department=request.form['department'],
                position=request.form['position'],
                salary=float(request.form['salary']),
                date_hired=datetime.strptime(request.form['date_hired'], '%Y-%m-%d').date(),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address')
            )
            
            # Handle photo upload (Check Base64 camera first, then fallback to File)
            photo_path = None
            upload_dir = os.path.join(current_app.root_path, 'static', 'employee_photos')
            os.makedirs(upload_dir, exist_ok=True)
            
            photo_base64 = request.form.get('photo_base64')
            if photo_base64:
                # Format is usually 'data:image/jpeg;base64,/9j/4AAQSkZ...'
                if ',' in photo_base64:
                    header, encoded = photo_base64.split(',', 1)
                    unique_filename = f"{uuid.uuid4().hex}.jpg"
                    save_path = os.path.join(upload_dir, unique_filename)
                    
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(encoded))
                    photo_path = save_path
                    employee.photo_path = f"employee_photos/{unique_filename}"
            elif 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file and photo_file.filename != '':
                    filename = secure_filename(photo_file.filename)
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
                    unique_filename = f"{uuid.uuid4().hex}.{ext}"
                    save_path = os.path.join(upload_dir, unique_filename)
                    
                    photo_file.save(save_path)
                    photo_path = save_path
                    employee.photo_path = f"employee_photos/{unique_filename}"
                    
            # Process background cleaning and resizing if a photo was successfully saved
            if photo_path and os.path.exists(photo_path):
                cleaned_filename = clean_employee_photo(photo_path, upload_dir)
                employee.photo_path = f"employee_photos/{cleaned_filename}"
                
                # Clean up the raw upload since we have the processed version
                if os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                    except:
                        pass
            
            db.session.add(employee)
            db.session.commit()
            
            flash(f'Employee {employee.first_name} {employee.last_name} added successfully!', 'success')
            return redirect(url_for('employees.list_employees'))
            
        except Exception as e:
            flash(f'Error adding employee: {str(e)}', 'error')
            return redirect(url_for('employees.add_employee'))
    
    return render_template('employees/add.html')

@employee_bp.route('/edit/<int:employee_id>', methods=['GET', 'POST'])
@login_required
@hr_required
def edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    if request.method == 'POST':
        try:
            employee.first_name = request.form['first_name']
            employee.last_name = request.form['last_name']
            employee.department = request.form['department']
            employee.position = request.form['position']
            employee.salary = float(request.form['salary'])
            employee.date_hired = datetime.strptime(request.form['date_hired'], '%Y-%m-%d').date()
            employee.phone = request.form.get('phone')
            employee.email = request.form.get('email')
            employee.address = request.form.get('address')
            employee.status = request.form.get('status', 'Active')
            
            # Handle photo upload (Check Base64 camera first, then fallback to File)
            photo_path = None
            upload_dir = os.path.join(current_app.root_path, 'static', 'employee_photos')
            os.makedirs(upload_dir, exist_ok=True)
            
            photo_base64 = request.form.get('photo_base64')
            if photo_base64:
                if ',' in photo_base64:
                    header, encoded = photo_base64.split(',', 1)
                    unique_filename = f"{uuid.uuid4().hex}.jpg"
                    save_path = os.path.join(upload_dir, unique_filename)
                    
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(encoded))
                    photo_path = save_path
                    employee.photo_path = f"employee_photos/{unique_filename}"
            elif 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file and photo_file.filename != '':
                    filename = secure_filename(photo_file.filename)
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
                    unique_filename = f"{uuid.uuid4().hex}.{ext}"
                    save_path = os.path.join(upload_dir, unique_filename)
                    
                    photo_file.save(save_path)
                    photo_path = save_path
                    employee.photo_path = f"employee_photos/{unique_filename}"
            
            # Process background cleaning and resizing if a photo was successfully saved
            if photo_path and os.path.exists(photo_path):
                cleaned_filename = clean_employee_photo(photo_path, upload_dir)
                employee.photo_path = f"employee_photos/{cleaned_filename}"
                
                # Clean up the raw upload since we have the processed version
                if os.path.exists(photo_path):
                    try:
                        os.remove(photo_path)
                    except:
                        pass
            
            db.session.commit()
            
            flash(f'Employee {employee.first_name} {employee.last_name} updated successfully!', 'success')
            return redirect(url_for('employees.list_employees'))
            
        except Exception as e:
            flash(f'Error updating employee: {str(e)}', 'error')
            return redirect(url_for('employees.edit_employee', employee_id=employee_id))
    
    return render_template('employees/edit.html', employee=employee)

@employee_bp.route('/delete/<int:employee_id>', methods=['POST'])
@login_required
@hr_required
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    try:
        employee.status = 'Deleted'
        if hasattr(employee, 'date_dismissed'):
            employee.date_dismissed = date.today()
            
        record = DisciplinaryRecord(
            employee_id=employee_id,
            action_type='Deleted'
        )
        db.session.add(record)
        db.session.commit()
        
        flash(f'Employee {employee.first_name} {employee.last_name} has been deleted', 'success')
        return redirect(url_for('employees.disciplinary_list'))
        
    except Exception as e:
        flash(f'Error deleting employee: {str(e)}', 'error')
        return redirect(url_for('employees.list_employees'))

@employee_bp.route('/dismiss/<int:employee_id>', methods=['POST'])
@login_required
@hr_required
def dismiss_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    try:
        employee.status = 'Dismissed'
        if hasattr(employee, 'date_dismissed'):
            employee.date_dismissed = date.today()
            
        record = DisciplinaryRecord(
            employee_id=employee_id,
            action_type='Dismissed'
        )
        db.session.add(record)
        db.session.commit()
        
        flash(f'Employee {employee.first_name} {employee.last_name} has been dismissed', 'success')
        return redirect(url_for('employees.disciplinary_list'))
        
    except Exception as e:
        flash(f'Error dismissing employee: {str(e)}', 'error')
        return redirect(url_for('employees.list_employees'))

@employee_bp.route('/interdict/<int:employee_id>', methods=['POST'])
@login_required
@hr_required
def interdict_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    try:
        employee.status = 'Interdicted'
        
        record = DisciplinaryRecord(
            employee_id=employee_id,
            action_type='Interdicted'
        )
        db.session.add(record)
        db.session.commit()
        
        flash(f'Employee {employee.first_name} {employee.last_name} has been placed on interdiction', 'success')
        return redirect(url_for('employees.disciplinary_list'))
        
    except Exception as e:
        flash(f'Error interdicting employee: {str(e)}', 'error')
        return redirect(url_for('employees.list_employees'))

@employee_bp.route('/reinstate/<int:record_id>', methods=['POST'])
@login_required
@hr_required
def reinstate_employee(record_id):
    from models import DisciplinaryRecord
    record = DisciplinaryRecord.query.get_or_404(record_id)
    employee = Employee.query.get(record.employee_id)
    
    if not employee:
        flash("Employee associated with this record not found.", "error")
        return redirect(url_for('employees.disciplinary_list'))
        
    try:
        employee.status = 'Active'
        if hasattr(employee, 'date_dismissed'):
            employee.date_dismissed = None
            
        # We can either delete the record or mark it as resolved.
        # Deleting it matches the user's requested logic flow.
        db.session.delete(record)
        db.session.commit()
        
        flash(f'Employee {employee.first_name} {employee.last_name} has been reinstated', 'success')
        return redirect(url_for('employees.list_employees'))
        
    except Exception as e:
        flash(f'Error reinstating employee: {str(e)}', 'error')
        return redirect(url_for('employees.disciplinary_list'))

@employee_bp.route('/disciplinary')
@login_required
@hr_required
def disciplinary_list():
    from models import DisciplinaryRecord
    records = DisciplinaryRecord.query.order_by(DisciplinaryRecord.action_date.desc()).all()
    return render_template('employees/disciplinary.html', records=records)

@employee_bp.route('/view/<int:employee_id>')
@login_required
def view_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    # Get payroll history
    payroll_history = Payroll.query.filter_by(employee_id=employee_id).order_by(Payroll.created_at.desc()).limit(12).all()
    
    # Get attendance records
    attendance_records = Attendance.query.filter_by(employee_id=employee_id).order_by(Attendance.date.desc()).limit(30).all()
    
    # Get active loans
    from models import EmployeeLoan
    loans = EmployeeLoan.query.filter_by(employee_id=employee_id).all()
    
    return render_template('employees/view.html', 
                         employee=employee, 
                         payroll_history=payroll_history,
                         attendance_records=attendance_records,
                         loans=loans)

@employee_bp.route('/id_card/<int:employee_id>')
@login_required
def generate_id_card(employee_id):
    from utils.pdf_utils import generate_dual_sided_id_card
    
    employee = Employee.query.get_or_404(employee_id)
    
    try:
        buffer = generate_dual_sided_id_card(employee)
        
        response = Response(buffer.getvalue(), mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment; filename=ID_Card_{employee.employment_number}.pdf'
        
        return response
    except Exception as e:
        flash(f'Error generating ID card: {str(e)}', 'error')
        return redirect(url_for('employees.view_employee', employee_id=employee_id))

@employee_bp.route('/generate_all_id_cards')
@login_required
def generate_all_id_cards():
    from utils.pdf_utils import generate_bulk_id_cards
    
    employees = Employee.query.filter_by(status='Active').all()
    if not employees:
        flash('No active employees found to generate ID cards.', 'warning')
        return redirect(url_for('employees.list_employees'))
        
    try:
        buffer = generate_bulk_id_cards(employees)
        
        response = Response(buffer.getvalue(), mimetype='application/pdf')
        response.headers['Content-Disposition'] = 'attachment; filename=ALL_EMPLOYEE_ID_CARDS.pdf'
        
        return response
    except Exception as e:
        flash(f'Error generating bulk ID cards: {str(e)}', 'error')
        return redirect(url_for('employees.list_employees'))
