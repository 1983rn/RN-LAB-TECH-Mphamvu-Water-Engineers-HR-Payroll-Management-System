from flask import Blueprint, render_template, request, flash, redirect, url_for, session
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
from models import MDApprovalRequest
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

from flask import make_response

@hr_bp.route('/md_dashboard', methods=['GET'])
@login_required
def md_dashboard():
    if not session.get('md_logged_in'):
        flash("You must be logged in as the Managing Director to view this page.", "error")
        return redirect(url_for('hr.md_login'))
    
    employees_reqs = MDApprovalRequest.query.filter_by(module='Employees').order_by(MDApprovalRequest.request_time.desc()).all()
    payroll_reqs = MDApprovalRequest.query.filter_by(module='Payroll').order_by(MDApprovalRequest.request_time.desc()).all()
    
    response = make_response(render_template('hr/md_dashboard.html', employees_reqs=employees_reqs, payroll_reqs=payroll_reqs))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@hr_bp.route('/md_dashboard/approve/<int:req_id>', methods=['POST'])
@login_required
def approve_md_request(req_id):
    if not session.get('md_logged_in'):
        return redirect(url_for('hr.md_login'))
    
    action = request.form.get('action')
    req_obj = MDApprovalRequest.query.get_or_404(req_id)
    
    if action == 'approve':
        req_obj.status = 'Approved'
        req_obj.otp_code = generate_otp()
        req_obj.expires_at = datetime.utcnow() + timedelta(hours=2, minutes=30)
        flash(f"Approved {req_obj.requester_name}'s request. Give them the OTP code displayed.", "success")
    elif action == 'reject':
        req_obj.status = 'Rejected'
        flash(f"Rejected {req_obj.requester_name}'s request.", "info")
    elif action == 'delete':
        db.session.delete(req_obj)
        db.session.commit()
        flash(f"Removed log entry for {req_obj.requester_name}.", "info")
        return redirect(url_for('hr.md_dashboard'))
        
    db.session.commit()
    return redirect(url_for('hr.md_dashboard'))

@hr_bp.route('/gateway/<module>', methods=['GET'])
@login_required
def gateway(module):
    if module not in ['Employees', 'Payroll']:
        flash("Invalid module.", "error")
        return redirect(url_for('hr.dashboard'))
    response = make_response(render_template('hr/gateway.html', module=module))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@hr_bp.route('/request_access', methods=['POST'])
@login_required
def request_access():
    module = request.form.get('module')
    name = request.form.get('requester_name')
    
    if not name or not module:
        flash("All fields are required.", "error")
        return redirect(url_for('hr.gateway', module=module))
        
    # Create the request
    new_req = MDApprovalRequest(requester_name=name, module=module)
    db.session.add(new_req)
    db.session.commit()
    
    flash("Request sent to Managing Director. Please await approval and your distinct OTP.", "success")
    return redirect(url_for('hr.gateway', module=module))

@hr_bp.route('/verify_otp', methods=['POST'])
@login_required
def verify_otp():
    module = request.form.get('module')
    otp_code = request.form.get('otp_code', '').strip().upper()
    
    # Verify OTP against DB
    req_obj = MDApprovalRequest.query.filter_by(
        module=module,
        otp_code=otp_code,
        status='Approved',
        is_used=False
    ).first()
    
    if req_obj and req_obj.expires_at > datetime.utcnow():
        # Valid OTP
        req_obj.is_used = True
        db.session.commit()
        
        # Grant session access
        session_key = f"md_access_{module.lower()}"
        expiry_key = f"md_access_{module.lower()}_expiry"
        session[session_key] = True
        session[expiry_key] = (datetime.utcnow() + timedelta(hours=2, minutes=30)).isoformat()
        
        flash(f"Validation successful! Access to {module} granted for 2h 30m.", "success")
        
        if module == 'Employees':
            return redirect(url_for('employees.list_employees'))
        else:
            return redirect(url_for('payroll.payroll_list'))
            
    flash("Invalid, expired, or already-used OTP code. Please try again or request a new one.", "error")
    return redirect(url_for('hr.gateway', module=module))
