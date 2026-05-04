import sys
import os

# Ensure the project directory is in Python's module search path (needed for gunicorn)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

from db_utils import init_db
from models import db, User, Employee, Payroll, Attendance, Client, Quotation, Contract, Invoice, DeliveryNote, Transaction, SupportRequest
from config import Config

# Import blueprints
from documents.employees.employee_routes import employee_bp
from payroll.payroll_routes import payroll_bp
from attendance.attendance_routes import attendance_bp
from quotations.quotation_routes import quotations_bp
from accounts.invoice_routes import finance_bp
from accounts.transaction_routes import transaction_bp
from quotations.rfq_routes import rfq_bp
from clients.client_routes import clients_bp
from inventory.inventory_routes import inventory_bp
from farm.farm_routes import farm_bp
from accounts.dashboard_routes import accounts_bp
from construction.construction_routes import construction_bp
from rest_house.rest_house_routes import rest_house_bp
from borehole.borehole_routes import borehole_bp
from hr.hr_routes import hr_bp
from ict.ict_routes import ict_bp

app = Flask(__name__)
app.config.from_object(Config)

# Prioritize DATABASE_URL if available (for Render PostgreSQL), fallback to local SQLite
database_url = os.environ.get('DATABASE_URL', 'sqlite:///system.db')
# SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Add SSL requirements for Render PostgreSQL if not present
if "postgresql" in database_url and "sslmode" not in database_url:
    if "?" in database_url:
        database_url += "&sslmode=require"
    else:
        database_url += "?sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Initialize database and default admin on startup
with app.app_context():
    try:
        init_db()
        
        # Start Email RFQ fetching background daemon (if not in a worker that shouldn't)
        # On Render, background tasks might be better in a separate worker, but for simplicity:
        try:
            from utils.rfq_parser import start_background_task
            start_background_task()
        except Exception as e:
            app.logger.error(f"Failed to start background task: {e}")
        
        # ─── UNIVERSAL ADMIN INITIALIZATION (Local & Render) ───
        admin_username = 'Mphamvuwaterengineers'
        admin_password = '.org.ulandaduwe/2026/**?/'
        
        default_admin = User.query.filter_by(username=admin_username).first()
        
        if not default_admin:
            # Create new admin if missing
            default_admin = User(
                username=admin_username,
                password_hash=generate_password_hash(admin_password),
                role='Administrator',
                password_change_required=True
            )
            db.session.add(default_admin)
            db.session.commit()
            print(f"Created new default admin: {admin_username}")
        elif default_admin.password_change_required:
            # Force password synchronization if change is still required
            # This ensures both local and Render stay in sync with your provided credentials
            default_admin.password_hash = generate_password_hash(admin_password)
            db.session.commit()
            print(f"Synchronized admin password for: {admin_username}")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # On Render, printing to stdout shows up in logs

# Register blueprints
app.register_blueprint(employee_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(quotations_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(transaction_bp)
app.register_blueprint(rfq_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(farm_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(construction_bp)
app.register_blueprint(rest_house_bp)
app.register_blueprint(borehole_bp)
app.register_blueprint(hr_bp)
app.register_blueprint(ict_bp)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'Administrator':
            flash('Administrator access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_now():
    return {'datetime': datetime}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            user = User.query.filter_by(username=username).first()
            
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.user_id
                session['username'] = user.username
                session['role'] = user.role
                
                if user.password_change_required:
                    flash('Please change your password on first login', 'info')
                    return redirect(url_for('change_password'))
                
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')
        except Exception as e:
            app.logger.error(f"Login error: {e}")
            flash('A database error occurred. Please try again later.', 'error')
    
    return render_template('login.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        user = User.query.get(session['user_id'])
        
        if not check_password_hash(user.password_hash, current_password):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return redirect(url_for('change_password'))
        
        user.password_hash = generate_password_hash(new_password)
        user.password_change_required = False
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    from utils.auth_utils import apply_dept_filter
    from models import PayrollOTP
    role = session.get('role')
    
    try:
        stats = {
            'total_employees': Employee.query.count(),
            'active_employees': Employee.query.filter_by(status='Active').count(),
            'total_clients': apply_dept_filter(Client.query, Client).count(),
            'pending_quotations': apply_dept_filter(Quotation.query, Quotation).filter_by(status='Pending').count(),
            'approved_contracts': apply_dept_filter(Contract.query, Contract).filter_by(status='Approved').count(),
            'total_transactions': apply_dept_filter(Transaction.query, Transaction).count()
        }
    except Exception as e:
        app.logger.error(f"Dashboard stats error: {e}")
        stats = {k: 0 for k in ['total_employees', 'active_employees', 'total_clients', 'pending_quotations', 'approved_contracts', 'total_transactions']}
    
    # MD Context: Pending OTPs
    pending_otps = []
    if role == 'Director':
        try:
            pending_otps = PayrollOTP.query.filter_by(is_used=False).filter(PayrollOTP.expires_at > datetime.utcnow()).all()
        except Exception as e:
            app.logger.error(f"Dashboard OTP error: {e}")
    
    return render_template('dashboard.html', 
                         role=role, 
                         stats=stats,
                         pending_otps=pending_otps)

@app.route('/verify/<document_number>')
def verify_document(document_number):
    """Verify document authenticity via QR code"""
    from models import Invoice, Quotation, DeliveryNote, Payroll
    
    try:
        doc_type = document_number.split('-')[0]
        
        if doc_type == 'INV':
            invoice = Invoice.query.filter_by(invoice_id=int(document_number.split('-')[2])).first()
            if invoice:
                return f"""<h2>MPHAMVU WATER ENGINEERS</h2>
                <p><b>Document Type:</b> Invoice</p>
                <p><b>Document Number:</b> {document_number}</p>
                <p><b>Status:</b> <span style='color:green'>VALID</span></p>
                <p><b>Amount:</b> MWK {invoice.amount:,.2f}</p>"""
        elif doc_type == 'QTN':
            quotation = Quotation.query.filter_by(quotation_id=int(document_number.split('-')[2])).first()
            if quotation:
                return f"""<h2>MPHAMVU WATER ENGINEERS</h2>
                <p><b>Document Type:</b> Quotation</p>
                <p><b>Document Number:</b> {document_number}</p>
                <p><b>Client:</b> {quotation.client.client_name}</p>
                <p><b>Status:</b> <span style='color:green'>VALID</span></p>
                <p><b>Amount:</b> MWK {quotation.total_amount:,.2f}</p>"""
        elif doc_type == 'DN':
            delivery = DeliveryNote.query.filter_by(delivery_id=int(document_number.split('-')[2])).first()
            if delivery:
                return f"""<h2>MPHAMVU WATER ENGINEERS</h2>
                <p><b>Document Type:</b> Delivery Note</p>
                <p><b>Document Number:</b> {document_number}</p>
                <p><b>Status:</b> <span style='color:green'>VALID</span></p>"""
        elif doc_type == 'PAY':
            payroll = Payroll.query.filter_by(payroll_id=int(document_number.split('-')[2])).first()
            if payroll:
                return f"""<h2>MPHAMVU WATER ENGINEERS</h2>
                <p><b>Document Type:</b> Payslip</p>
                <p><b>Document Number:</b> {document_number}</p>
                <p><b>Status:</b> <span style='color:green'>VALID</span></p>"""
    except Exception as e:
        app.logger.error(f"Verification error: {e}")
    
    return "<h2>Invalid Document</h2><p style='color:red'>This document could not be verified.</p>"

@app.route('/submit_support_request', methods=['POST'])
def submit_support_request():
    try:
        support_request = SupportRequest(
            name=request.form['name'],
            email=request.form['email'],
            support_type=request.form['support_type'],
            message=request.form['message']
        )
        db.session.add(support_request)
        db.session.commit()
        flash('Support request submitted successfully! We will contact you soon.', 'success')
    except Exception as e:
        flash(f'Error submitting support request: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
