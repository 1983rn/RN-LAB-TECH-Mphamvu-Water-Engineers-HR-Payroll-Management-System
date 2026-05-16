from flask import Blueprint, render_template, request, flash, redirect, url_for, session, make_response
from functools import wraps
from models import Employee, Payroll, Attendance
from datetime import datetime, date

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # HR usually requires Administrator, HR Manager, or Director
        if session.get('role') not in ['Administrator', 'Director', 'HR Manager']:
            flash('You do not have permission to access the HR Department.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@hr_bp.route('/dashboard', methods=['GET'])
@login_required
@admin_required
def dashboard():
    # Set context for sidebar/navigation
    session['department_context'] = 'HR Department'
    session['department_dashboard'] = 'hr.dashboard'

    # Collect stats for the dashboard display
    total_employees = Employee.query.count()
    active_employees = Employee.query.filter_by(status='Active').count()
    on_leave = Employee.query.filter_by(status='On Leave').count()
    
    # Simple payroll stats
    pending_payroll = Payroll.query.filter_by(status='Pending').count()
    recent_payrolls = Payroll.query.order_by(Payroll.created_at.desc()).limit(5).all()

    # Get attendance data for today
    today = date.today()
    today_attendance = Attendance.query.filter_by(date=today).count()

    return render_template('hr/dashboard.html',
                           total_employees=total_employees,
                           active_employees=active_employees,
                           on_leave=on_leave,
                           pending_payroll=pending_payroll,
                           recent_payrolls=recent_payrolls,
                           today_attendance=today_attendance,
                           now=datetime.now())

# ==================================================
# MD APPROVAL MODULE
# ==================================================

from db_utils import db
from models import MDApprovalRequest, PageAuthorization, Employee
from datetime import timedelta
import string
import random

def generate_otp():
    """Generates a secure 6-character alphanumeric OTP"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@hr_bp.route('/md_login', methods=['GET', 'POST'])
@login_required
@admin_required
def md_login():
    if request.method == 'POST':
        password = request.form.get('md_password')
        if password == "**//mweepDUWE.":
            session['md_logged_in'] = True
            flash("Authorized access granted to MD Dashboard.", "success")
            return redirect(url_for('hr.md_dashboard'))
        else:
            flash("Unauthorized: Invalid MD authentication key.", "error")
    return render_template('hr/md_login.html')

from models import MDApprovalRequest, PageAuthorization, Employee, PayrollOTP, PayrollBatch

@hr_bp.route('/md_dashboard', methods=['GET'])
@login_required
def md_dashboard():
    if not session.get('md_logged_in'):
        flash("You must be logged in as the Managing Director to view this page.", "error")
        return redirect(url_for('hr.md_login'))
    
    # Access Control List & Active Logs
    from models import AccessLog
    authorizations = PageAuthorization.query.all()
    all_employees = Employee.query.filter_by(status='Active').all()
    
    # Get the 50 most recent access logs
    access_logs = AccessLog.query.order_by(AccessLog.time_in.desc()).limit(50).all()
    
    response = make_response(render_template('hr/md_dashboard.html', 
                                            authorizations=authorizations,
                                            access_logs=access_logs,
                                            all_employees=all_employees))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@hr_bp.route('/md_dashboard/manage_auth', methods=['POST'])
@login_required
def manage_authorizations():
    if not session.get('md_logged_in'):
        return redirect(url_for('hr.md_login'))
    
    action = request.form.get('action')
    if action == 'add':
        employee_id = request.form.get('employee_id')
        page_name = request.form.get('page_name')
        
        # Check if already exists
        exists = PageAuthorization.query.filter_by(employee_id=employee_id, page_name=page_name).first()
        if exists:
            flash("Authorization already exists for this employee and page.", "warning")
        else:
            # Check if the employee already has a secret code assigned
            existing_auth = PageAuthorization.query.filter_by(employee_id=employee_id).first()
            if existing_auth and existing_auth.secret_code:
                secret_code = existing_auth.secret_code
            else:
                # Generate a unique 4-digit numeric secret code
                while True:
                    secret_code = ''.join(random.choices(string.digits, k=4))
                    if not PageAuthorization.query.filter_by(secret_code=secret_code).first():
                        break
                        
            new_auth = PageAuthorization(employee_id=employee_id, page_name=page_name, secret_code=secret_code)
            db.session.add(new_auth)
            db.session.commit()
            flash(f"Employee added to ACL. Secret Code: {secret_code}", "success")
    elif action == 'remove':
        auth_id = request.form.get('auth_id')
        auth_obj = PageAuthorization.query.get_or_404(auth_id)
        db.session.delete(auth_obj)
        db.session.commit()
        flash("Authorization removed.", "info")
        
    return redirect(url_for('hr.md_dashboard'))

@hr_bp.route('/gateway/<module>', methods=['GET'])
@login_required
def gateway(module):
    valid_modules = ['Employees', 'Payroll', 'Payslip', 'Accounts', 'Project_Tracking']
    if module not in valid_modules:
        flash("Invalid module.", "error")
        return redirect(url_for('hr.dashboard'))
    response = make_response(render_template('hr/gateway.html', module=module))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@hr_bp.route('/delete_access_log/<int:log_id>', methods=['POST'])
@login_required
def delete_access_log(log_id):
    if not session.get('md_logged_in'):
        flash("MD access required.", "error")
        return redirect(url_for('hr.md_login'))
    
    from models import AccessLog
    log = AccessLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    flash(f"Access log for '{log.personnel_name}' removed.", "info")
    return redirect(url_for('hr.md_dashboard'))

@hr_bp.route('/clear_all_access_logs', methods=['POST'])
@login_required
def clear_all_access_logs():
    if not session.get('md_logged_in'):
        flash("MD access required.", "error")
        return redirect(url_for('hr.md_login'))
    
    from models import AccessLog
    AccessLog.query.delete()
    db.session.commit()
    flash("All access logs cleared.", "info")
    return redirect(url_for('hr.md_dashboard'))

@hr_bp.route('/gateway_logout', methods=['GET'])
@login_required
def gateway_logout():
    module = request.args.get('module')
    name = session.get('authorized_personnel_name')
    
    if module and name:
        from models import AccessLog
        active_logs = AccessLog.query.filter_by(personnel_name=name, module=module, is_active=True).all()
        for log in active_logs:
            log.is_active = False
            log.time_out = datetime.utcnow()
        db.session.commit()
        
        session_key = f"md_access_{module.lower()}"
        expiry_key = f"md_access_{module.lower()}_expiry"
        session.pop(session_key, None)
        session.pop(expiry_key, None)
        
        flash(f"Successfully logged out of {module}.", "success")
    return redirect(url_for('hr.dashboard'))

@hr_bp.route('/request_access', methods=['POST'])
@login_required
def request_access():
    module = request.form.get('module')
    name = request.form.get('requester_name')
    secret_code = request.form.get('secret_code', '').strip()
    
    if not name or not module or not secret_code:
        flash("All fields including the 4-digit secret code are required.", "error")
        return redirect(url_for('hr.gateway', module=module))
    
    # MD Master Key bypass — the MD can use their authentication key to access any page
    MD_AUTH_KEY = "**//mweepDUWE."
    MD_NAME = "ULANDA DUWE"
    is_md = (secret_code == MD_AUTH_KEY and name.strip().upper() == MD_NAME)
    
    auth = None
    if not is_md:
        # Check if this person is authorized by MD in ACL AND has the correct secret code
        name_lower = name.lower()
        auth = PageAuthorization.query.join(Employee).filter(
            db.func.lower(Employee.first_name + ' ' + Employee.last_name) == name_lower,
            PageAuthorization.page_name == module,
            PageAuthorization.secret_code == secret_code,
            PageAuthorization.is_authorized == True
        ).first()
        
        if not auth and session.get('role') != 'Director':
            # Fallback: Check Python side in case DB concat lowercase fails on some SQLite drivers
            all_auths = PageAuthorization.query.join(Employee).filter(
                PageAuthorization.page_name == module,
                PageAuthorization.secret_code == secret_code,
                PageAuthorization.is_authorized == True
            ).all()
            for a in all_auths:
                if f"{a.employee.first_name} {a.employee.last_name}".lower() == name_lower:
                    auth = a
                    break
                    
        if not auth and session.get('role') != 'Director':
            flash(f"Unauthorized: Verification failed for '{name}'. Please check your name and 4-digit secret code.", "error")
            return redirect(url_for('hr.gateway', module=module))
        
    # Grant session access directly via Secret Code
    session_key = f"md_access_{module.lower()}"
    expiry_key = f"md_access_{module.lower()}_expiry"
    from datetime import timedelta
    session[session_key] = True
    session[expiry_key] = (datetime.utcnow() + timedelta(hours=2, minutes=30)).isoformat()
    
    # Store personnel name in session to log them out later if needed
    session['authorized_personnel_name'] = name
    
    # Create an access log
    from models import AccessLog
    # First, close any active logs for this person and module
    active_logs = AccessLog.query.filter_by(personnel_name=name, module=module, is_active=True).all()
    for log in active_logs:
        log.is_active = False
        log.time_out = datetime.utcnow()
        
    new_log = AccessLog(
        personnel_name=name,
        module=module,
        is_active=True
    )
    db.session.add(new_log)
    db.session.commit()
    
    flash(f"Access to {module} granted for 2h 30m.", "success")
    
    if module == 'Employees':
        return redirect(url_for('employees.list_employees'))
    elif module == 'Payroll':
        return redirect(url_for('payroll.payroll_list'))
    elif module == 'Payslip':
        return redirect(url_for('payroll.payslip_center'))
    elif module == 'Accounts':
        return redirect(url_for('accounts.dashboard'))
    elif module == 'Project_Tracking':
        return redirect(url_for('hr.project_tracking'))
        
    return redirect(url_for('hr.dashboard'))
@hr_bp.route('/project_tracking', methods=['GET'])
@login_required
@admin_required
def project_tracking():
    from models import ConstructionProject, ICTProject, FarmActivity, CropCycle, Quotation
    from datetime import date
    
    today = date.today()
    
    # Fetch all project types
    construction_projects = ConstructionProject.query.all()
    ict_projects = ICTProject.query.all()
    farm_activities = FarmActivity.query.all()
    crop_cycles = CropCycle.query.all()
    
    # Fetch ALL quotations to separate into Pending vs Approved (Awarded)
    all_quotations = Quotation.query.all()
    
    # Unified structure
    projects = {
        'Borehole Drilling': {'pending_award': [], 'underway': [], 'completed': [], 'overdue': []},
        'Construction': {'pending_award': [], 'underway': [], 'completed': [], 'overdue': []},
        'Farm': {'pending_award': [], 'underway': [], 'completed': [], 'overdue': []},
        'ICT': {'pending_award': [], 'underway': [], 'completed': [], 'overdue': []}
    }
    
    # helper for department mapping
    def get_target_dept(dept_name):
        d = (dept_name or '').strip().lower()
        if 'construction' in d: return 'Construction'
        if 'ict' in d: return 'ICT'
        if 'farm' in d: return 'Farm'
        return 'Borehole Drilling'

    # Process Quotations
    for q in all_quotations:
        dept = get_target_dept(q.department)
        
        if q.status == 'Approved':
            # Awarded! Use contract dates entered during approval
            from models import Contract
            contract = Contract.query.filter_by(quotation_id=q.quotation_id).order_by(Contract.created_at.desc()).first()
            
            # If for some reason there's no contract, we still show it but with N/A dates
            # instead of falling back to quotation creation date
            data = {
                'type': 'Awarded Quotation',
                'id': q.quotation_id,
                'name': q.client.client_name if q.client else 'Unknown',
                'amount': q.total_amount,
                'start': contract.start_date if contract else None,
                'end': contract.end_date if contract else None,
                'status': 'Approved'
            }
            
            # Determine tracking category
            end_date = data['end']
            if end_date and end_date < today:
                projects[dept]['overdue'].append(data)
            else:
                projects[dept]['underway'].append(data)
                
        elif q.status not in ['Rejected', 'Completed']:
            # Pending Award - these go to "Available Quotations"
            projects[dept]['pending_award'].append({
                'type': 'Quotation',
                'id': q.quotation_id,
                'name': q.client.client_name if q.client else 'Unknown',
                'amount': q.total_amount,
                'location': q.project_location,
                'date': q.created_at,
                'status': q.status
            })
    
    def process_project(p, dept, name, end_date_attr='end_date'):
        status = getattr(p, 'status', '').lower()
        end_date = getattr(p, end_date_attr, None)
        
        # Determine if awarded
        is_pending = status in ['planning', 'planned', 'pending']
        
        data = {
            'type': 'Project',
            'name': name,
            'start': getattr(p, 'start_date', None) or getattr(p, 'planting_date', None),
            'end': end_date,
            'status': p.status
        }
        
        if is_pending:
            projects[dept]['pending_award'].append(data)
        elif status in ['completed', 'harvested']:
            projects[dept]['completed'].append(data)
        elif end_date and end_date < today:
            projects[dept]['overdue'].append(data)
        else:
            projects[dept]['underway'].append(data)

    # Process all departments
    for p in construction_projects:
        dept = p.department if p.department in projects else 'Construction'
        process_project(p, dept, p.project_name)
        
    for p in ict_projects:
        process_project(p, 'ICT', p.project_name)
        
    for p in farm_activities:
        process_project(p, 'Farm', p.activity_name)
        
    for p in crop_cycles:
        process_project(p, 'Farm', f"Crop: {p.crop_name}", 'expected_harvest_date')

    return render_template('hr/project_tracking.html', projects=projects, today=today)
