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
from employees.employee_routes import employee_bp
from payroll.payroll_routes import payroll_bp
from attendance.attendance_routes import attendance_bp
from quotations.quotation_routes import quotations_bp
from finance.invoice_routes import finance_bp
from finance.transaction_routes import transaction_bp

app = Flask(__name__)
app.config.from_object(Config)

# Prioritize DATABASE_URL if available (for Render PostgreSQL), fallback to local SQLite
database_url = os.environ.get('DATABASE_URL', 'sqlite:///system.db')
# SQLAlchemy 1.4+ requires 'postgresql://' instead of 'postgres://'
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Register blueprints
app.register_blueprint(employee_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(quotations_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(transaction_bp)

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
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
    role = session.get('role')
    
    stats = {
        'total_employees': Employee.query.count(),
        'active_employees': Employee.query.filter_by(status='Active').count(),
        'total_clients': Client.query.count(),
        'pending_quotations': Quotation.query.filter_by(status='Pending').count(),
        'approved_contracts': Contract.query.filter_by(status='Approved').count(),
        'total_transactions': Transaction.query.count()
    }
    
    return render_template('dashboard.html', 
                         role=role, 
                         stats=stats)

@app.route('/verify/<document_number>')
def verify_document(document_number):
    """Verify document authenticity via QR code"""
    from models import Invoice, Quotation, DeliveryNote, Payroll
    
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

# Initialize database and default admin on import (works with gunicorn)
with app.app_context():
    init_db()
    
    default_admin = User.query.filter_by(username='Mphamvuwaterengineers').first()
    if not default_admin:
        default_admin = User(
            username='Mphamvuwaterengineers',
            password_hash=generate_password_hash('.org.ulandaduwe/2026/**?'),
            role='Administrator',
            password_change_required=True
        )
        db.session.add(default_admin)
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
