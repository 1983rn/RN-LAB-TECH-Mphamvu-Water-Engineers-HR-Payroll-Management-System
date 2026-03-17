from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from db_utils import db, get_reference_number

class User(db.Model):
    __tablename__ = 'users'
    
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Employee')
    password_change_required = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(20), default='Active')

class Employee(db.Model):
    __tablename__ = 'employees'
    
    employee_id = db.Column(db.Integer, primary_key=True)
    employment_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    salary = db.Column(db.Float, nullable=False)
    date_hired = db.Column(db.Date, nullable=False)
    date_dismissed = db.Column(db.Date)
    status = db.Column(db.String(20), default='Active')
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    photo_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('EMP'))

class Payroll(db.Model):
    __tablename__ = 'payroll'
    
    payroll_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    payroll_month = db.Column(db.String(20), nullable=False)
    basic_salary = db.Column(db.Float, nullable=False)
    allowances = db.Column(db.Float, default=0)
    payee_tax = db.Column(db.Float, default=0)
    loan_deduction = db.Column(db.Float, default=0)
    deductions = db.Column(db.Float, default=0) # Other general deductions
    taxes = db.Column(db.Float, default=0) # Total taxes (including payee if not overridden)
    net_salary = db.Column(db.Float, nullable=False)
    absentee_deduction = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='Processed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('PAY'))
    
    employee = db.relationship('Employee', backref='payrolls')

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    attendance_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # Present, Absent, Late, Half Day
    check_in = db.Column(db.Time)
    check_out = db.Column(db.Time)
    late_minutes = db.Column(db.Integer, default=0)
    overtime_minutes = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('ATT'))
    
    employee = db.relationship('Employee', backref='attendances')

class Client(db.Model):
    __tablename__ = 'clients'
    
    client_id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    address = db.Column(db.Text, nullable=False)
    project_type = db.Column(db.String(100), nullable=False)
    quotation_amount = db.Column(db.Float, default=0)
    contract_status = db.Column(db.String(20), default='Pending')
    payment_status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('CLI'))

class Quotation(db.Model):
    __tablename__ = 'quotations'
    
    quotation_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    project_location = db.Column(db.String(200), nullable=False)
    borehole_depth = db.Column(db.Float)
    equipment_cost = db.Column(db.Float, default=0)
    labour_cost = db.Column(db.Float, default=0)
    transport_cost = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    validity_days = db.Column(db.Integer, default=30)
    description = db.Column(db.Text, default='We have pleasure in quoting our prices for borehole development as follows;')
    status = db.Column(db.String(20), default='Pending')
    delivery_confirmed = db.Column(db.Boolean, default=False)
    delivery_approved_by = db.Column(db.String(100))
    delivery_approved_date = db.Column(db.DateTime)
    invoice_generated = db.Column(db.Boolean, default=False)
    delivery_note_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('QUO'))
    
    client = db.relationship('Client', backref='quotations')
    quotation_items = db.relationship('QuotationItem', backref='quotation', cascade='all, delete-orphan')

class QuotationItem(db.Model):
    __tablename__ = 'quotation_items'
    
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.quotation_id'), nullable=False)
    project_type = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(50))
    quantity = db.Column(db.Float, nullable=False)
    unit_rate = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)

class Contract(db.Model):
    __tablename__ = 'contracts'
    
    contract_id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.quotation_id'), nullable=False)
    contract_date = db.Column(db.Date, nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='Pending')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('CON'))
    
    quotation = db.relationship('Quotation', backref='contracts')

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    invoice_id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.contract_id'), nullable=True) # Changed to True if some don't have contracts
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.quotation_id'))
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='Unpaid')
    payment_terms = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('INV'))
    
    contract = db.relationship('Contract', backref='invoices')
    quotation = db.relationship('Quotation', backref='invoices_list')

class DeliveryNote(db.Model):
    __tablename__ = 'delivery_notes'
    
    delivery_id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.invoice_id'), nullable=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.quotation_id'))
    delivery_date = db.Column(db.Date, nullable=False)
    equipment_delivered = db.Column(db.Text, nullable=False)
    delivered_by = db.Column(db.String(100), nullable=False)
    received_by = db.Column(db.String(100))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='Delivered')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('DEL'))
    
    invoice = db.relationship('Invoice', backref='delivery_notes_list')
    quotation = db.relationship('Quotation', backref='delivery_notes_list')

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    transaction_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.invoice_id'))
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    transaction_reference = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Completed')
    bank_account = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('TRX'))
    
    client = db.relationship('Client', backref='transactions')
    invoice = db.relationship('Invoice', backref='transactions')

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    notification_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'))
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'))
    type = db.Column(db.String(50), nullable=False)  # Email, SMS
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('NOT'))
    
    client = db.relationship('Client', backref='notifications')
    employee = db.relationship('Employee', backref='notifications')

class SupportRequest(db.Model):
    __tablename__ = 'support_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    support_type = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EmployeeLoan(db.Model):
    __tablename__ = 'employee_loans'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    employment_no = db.Column(db.String(50)) # For compatibility with directive logic
    loan_amount = db.Column(db.Float, default=0)
    repayment_months = db.Column(db.Integer, default=1)
    monthly_deduction = db.Column(db.Float, default=0)
    amount_paid = db.Column(db.Float, default=0)
    balance = db.Column(db.Float, default=0)
    start_date = db.Column(db.String(50)) # Using string as per directive's SQL example
    status = db.Column(db.String(20), default='Active') # Active, Paid
    
    employee = db.relationship('Employee', backref='loans')

class DisciplinaryRecord(db.Model):
    __tablename__ = 'disciplinary_records'
    
    record_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # Dismissed, Interdicted, Deleted
    reason = db.Column(db.Text)
    action_date = db.Column(db.Date, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='disciplinary_records')
