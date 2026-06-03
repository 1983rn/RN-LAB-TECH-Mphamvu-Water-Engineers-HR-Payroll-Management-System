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
    bank_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    airtel_number = db.Column(db.String(20))
    tnm_mpamba_number = db.Column(db.String(20))
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
    total_transactions = db.Column(db.Integer, default=0)
    completed_transactions = db.Column(db.Integer, default=0)
    on_time_payments = db.Column(db.Integer, default=0)
    defaults = db.Column(db.Integer, default=0)
    credit_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    department = db.Column(db.String(100), default='Borehole Drilling', nullable=False)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('CLI'))

class Quotation(db.Model):
    __tablename__ = 'quotations'
    
    quotation_id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    project_location = db.Column(db.String(200), nullable=False)
    project_latitude = db.Column(db.Float, nullable=True)
    project_longitude = db.Column(db.Float, nullable=True)
    borehole_depth = db.Column(db.Float)
    equipment_cost = db.Column(db.Float, default=0)
    labour_cost = db.Column(db.Float, default=0)
    transport_cost = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, nullable=False)
    validity_days = db.Column(db.Integer, default=30)
    description = db.Column(db.Text, default='We have pleasure in quoting our prices for borehole development as follows;')
    footnote = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending')
    delivery_confirmed = db.Column(db.Boolean, default=False)
    delivery_approved_by = db.Column(db.String(100))
    delivery_approved_date = db.Column(db.DateTime)
    invoice_generated = db.Column(db.Boolean, default=False)
    delivery_note_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('QUO'))
    department = db.Column(db.String(100), default='Borehole Drilling', nullable=False)
    
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

class CustomProjectType(db.Model):
    __tablename__ = 'custom_project_types'
    
    id = db.Column(db.Integer, primary_key=True)
    project_type = db.Column(db.String(200), unique=True, nullable=False)
    department = db.Column(db.String(100), default='Borehole')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustomInventoryCategory(db.Model):
    __tablename__ = 'custom_inventory_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(200), unique=True, nullable=False)
    department = db.Column(db.String(100), default='Farm')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    department = db.Column(db.String(100), default='Borehole Drilling', nullable=False)
    
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
    is_approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.String(100))
    approved_date = db.Column(db.DateTime)
    payment_terms = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reference_number = db.Column(db.String(50), unique=True, default=lambda: get_reference_number('INV'))
    department = db.Column(db.String(100), default='Borehole Drilling', nullable=False)
    project_name = db.Column(db.String(255), nullable=True)
    
    contract = db.relationship('Contract', backref='invoices')
    quotation = db.relationship('Quotation', backref='invoices_list')

    @property
    def latest_transaction(self):
        return Transaction.query.filter_by(invoice_id=self.invoice_id).order_by(Transaction.payment_date.desc()).first()

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
    department = db.Column(db.String(100), default='Borehole Drilling', nullable=False)
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
    department = db.Column(db.String(100), default='Borehole Drilling')
    
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

class RFQRequest(db.Model):
    __tablename__ = 'rfq_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    client = db.Column(db.String(200))
    location = db.Column(db.String(200))
    item = db.Column(db.String(200))
    description = db.Column(db.Text)
    unit = db.Column(db.String(50))
    qty = db.Column(db.Float)
    unit_rate = db.Column(db.Float)
    total = db.Column(db.Float)
    source = db.Column(db.String(50))  # 'facebook' or 'email'
    status = db.Column(db.String(20), default='pending') # 'pending' or 'processed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RFQResponse(db.Model):
    __tablename__ = 'rfq_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(50), unique=True, index=True)
    company = db.Column(db.String(200))
    contact = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    reg_no = db.Column(db.String(100))
    water_reg_no = db.Column(db.String(100))
    location = db.Column(db.String(200))
    work_required = db.Column(db.Text)
    yield_value = db.Column(db.String(50))  # Min yield in liters/sec
    warranty_borehole = db.Column(db.String(50))  # Warranty in years
    warranty_pump = db.Column(db.String(50))  # Warranty in years
    days_to_complete = db.Column(db.String(50))
    deposit = db.Column(db.String(50))
    balance_condition = db.Column(db.String(200))
    validity_days = db.Column(db.String(50))
    table_data = db.Column(db.Text)  # JSON string of table data (headers, rows, footer)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    department = db.Column(db.String(100), default='Borehole Drilling', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='rfq_responses')
    company_documents = db.relationship(
        'RFQResponseCompanyDocument',
        backref='rfq_response',
        lazy=True,
        cascade='all, delete-orphan',
    )

class RFQResponseCompanyDocument(db.Model):
    """
    Stores uploaded company-related documents/certificates for a single RFQ response.
    We persist them so the UI can preview/download and the generated RFQ PDF can reference/append them.
    """
    __tablename__ = 'rfq_response_company_documents'

    id = db.Column(db.Integer, primary_key=True)
    rfq_response_id = db.Column(
        db.Integer,
        db.ForeignKey('rfq_responses.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    filename = db.Column(db.String(255), nullable=False)  # Original client filename
    storage_path = db.Column(db.String(1000), nullable=False)  # Absolute path on disk
    mime_type = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# ENTERPRISE MODULES
# ==========================================

class ClientCreditScore(db.Model):
    __tablename__ = 'client_credit_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.String(50), nullable=False)
    repayment_chance = db.Column(db.String(50), nullable=False)
    interpretation = db.Column(db.Text, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = db.relationship('Client', backref=db.backref('credit_scores', lazy=True, cascade='all, delete-orphan'))

class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100))
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit_value = db.Column(db.Float, nullable=False, default=0.0)
    total_value = db.Column(db.Float, nullable=False, default=0.0)
    condition = db.Column(db.String(100), default='New/Excellent/Good')
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    department = db.Column(db.String(100), default='Borehole Drilling', nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FarmActivity(db.Model):
    __tablename__ = 'farm_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    activity_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='Planned')
    department = db.Column(db.String(100), default='Farm', nullable=False)
    profit = db.Column(db.Float, default=0.0)
    
    inputs = db.relationship('FarmInput', backref='activity_ref', lazy=True, cascade="all, delete-orphan")
    outputs = db.relationship('FarmOutput', backref='activity_ref', lazy=True, cascade="all, delete-orphan")
    expenses = db.relationship('FarmExpense', backref='activity_ref', lazy=True, cascade="all, delete-orphan")

    def update_profit(self):
        total_income = sum(output.total_value for output in self.outputs) if self.outputs else 0.0
        total_expense = sum(expense.amount for expense in self.expenses) if self.expenses else 0.0
        self.profit = total_income - total_expense

class Livestock(db.Model):
    __tablename__ = 'livestock'
    
    id = db.Column(db.Integer, primary_key=True)
    animal_type = db.Column(db.String(100), nullable=False) # Goat, Pig, Cattle, Poultry
    tag_number = db.Column(db.String(50), unique=True)
    gender = db.Column(db.String(20))
    breed = db.Column(db.String(100))
    birth_date = db.Column(db.Date)
    death_date = db.Column(db.Date)
    purchase_price = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default='Alive') # Alive, Dead, Sold, Butchered
    department = db.Column(db.String(100), default='Farm', nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CropCycle(db.Model):
    __tablename__ = 'crop_cycles'
    
    id = db.Column(db.Integer, primary_key=True)
    crop_name = db.Column(db.String(100), nullable=False) # Corn, Soybeans, etc.
    variety = db.Column(db.String(100))
    planting_date = db.Column(db.Date)
    expected_harvest_date = db.Column(db.Date)
    actual_harvest_date = db.Column(db.Date)
    quantity_harvested = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(50), default='Bags')
    status = db.Column(db.String(50), default='Growing') # Growing, Harvested, Failed
    department = db.Column(db.String(100), default='Farm', nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FarmInput(db.Model):
    __tablename__ = 'farm_inputs'
    
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('farm_activities.id'), nullable=True) # Optional link to activity
    item_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100)) # Feed, Medicine, Fertilizer, Seeds, Pesticides
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(50))
    unit_price = db.Column(db.Float, default=0.0)
    total_cost = db.Column(db.Float, default=0.0)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    department = db.Column(db.String(100), default='Farm')

class FarmOutput(db.Model):
    __tablename__ = 'farm_outputs'
    
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('farm_activities.id'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(50))
    unit_price = db.Column(db.Float, default=0.0)
    total_value = db.Column(db.Float, default=0.0)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    department = db.Column(db.String(100), default='Farm')

class FarmExpense(db.Model):
    __tablename__ = 'farm_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('farm_activities.id'), nullable=True)
    expense_category = db.Column(db.String(100))
    description = db.Column(db.Text)
    amount = db.Column(db.Float, default=0.0)
    department = db.Column(db.String(100), default='Farm', nullable=False)
    expense_date = db.Column(db.Date)

class CashBookEntry(db.Model):
    __tablename__ = 'cash_book_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(255), nullable=False)
    reference = db.Column(db.String(50))
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'Credit' or 'Debit'
    category = db.Column(db.String(100))
    department = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ==========================================
# CONSTRUCTION MODULE
# ==========================================

class ConstructionProject(db.Model):
    __tablename__ = 'construction_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    location = db.Column(db.String(200))
    project_latitude = db.Column(db.Float, nullable=True)
    project_longitude = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text)
    estimated_budget = db.Column(db.Float, default=0.0)
    actual_cost = db.Column(db.Float, default=0.0)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='Planning') # Planning, In Progress, Completed, Suspended
    department = db.Column(db.String(100), default='Construction', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref='construction_projects')
    costs = db.relationship('ConstructionCost', backref='project_ref', lazy=True, cascade="all, delete-orphan")

    def update_actual_cost(self):
        self.actual_cost = sum(cost.amount for cost in self.costs) if self.costs else 0.0

class ConstructionCost(db.Model):
    __tablename__ = 'construction_costs'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('construction_projects.id'), nullable=False)
    cost_type = db.Column(db.String(100)) # Labour, Transport, Raw Materials, Services
    description = db.Column(db.Text)
    amount = db.Column(db.Float, default=0.0)
    date = db.Column(db.Date, default=datetime.utcnow)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

class ConstructionStock(db.Model):
    __tablename__ = 'construction_stock'
    
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(200), nullable=False) # Cement, Bricks, etc.
    category = db.Column(db.String(100), default='Materials')
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(50)) # Bags, Pieces, Loads
    unit_price = db.Column(db.Float, default=0.0)
    total_value = db.Column(db.Float, default=0.0)
    last_restock_date = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    department = db.Column(db.String(100), default='Construction')

# ==========================================
# LODGE MODULE
# ==========================================

class LodgeRoom(db.Model):
    __tablename__ = 'lodge_rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False)
    room_type = db.Column(db.String(50), nullable=False, default='Single')  # Single, Double, Twin, Suite, Family
    price_per_night = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(30), default='Available')  # Available, Occupied, Maintenance, Reserved
    amenities = db.Column(db.Text)  # Comma-separated: AC, WiFi, TV, etc.
    description = db.Column(db.Text)
    floor = db.Column(db.String(20))
    max_guests = db.Column(db.Integer, default=2)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bookings = db.relationship('LodgeBooking', backref='room', lazy=True)

class LodgeCustomer(db.Model):
    __tablename__ = 'lodge_customers'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    id_number = db.Column(db.String(50))  # National ID or Passport
    nationality = db.Column(db.String(100), default='Malawian')
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bookings = db.relationship('LodgeBooking', backref='customer', lazy=True)

class LodgeBooking(db.Model):
    __tablename__ = 'lodge_bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('lodge_customers.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('lodge_rooms.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    num_guests = db.Column(db.Integer, default=1)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default='Confirmed')  # Confirmed, Checked-In, Checked-Out, Cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = db.relationship('LodgePayment', backref='booking', lazy=True)

class LodgePayment(db.Model):
    __tablename__ = 'lodge_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('lodge_bookings.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default='Cash')  # Cash, Bank Transfer, Mobile Money
    payment_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    reference = db.Column(db.String(100))
    status = db.Column(db.String(30), default='Completed')  # Completed, Pending, Refunded
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LodgeExpense(db.Model):
    __tablename__ = 'lodge_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), default='Operations')  # Utilities, Maintenance, Supplies, Staff, Food, Other
    amount = db.Column(db.Float, nullable=False, default=0.0)
    expense_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LodgeInventory(db.Model):
    __tablename__ = 'lodge_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False, default='Furniture')  # Beds, Furniture, Linen, Electronics, Kitchen, Toiletries
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit_value = db.Column(db.Float, default=0.0)
    total_value = db.Column(db.Float, default=0.0)
    condition = db.Column(db.String(50), default='Good')  # New, Good, Fair, Poor
    location = db.Column(db.String(200))  # Which room or storage area
    description = db.Column(db.Text)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ==========================================
# ACCOUNTS & PAYROLL WORKFLOW MODULES
# ==========================================

class PayrollBatch(db.Model):
    __tablename__ = 'payroll_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(20), nullable=False) # YYYY-MM
    status = db.Column(db.String(50), default='Draft') # Draft, Sent to SHR, Approved by SHR, Processing, Paid
    accounts_personnel = db.Column(db.String(100))
    shr_approved_by = db.Column(db.String(100))
    shr_approved_at = db.Column(db.DateTime)
    chief_accounts_approved_by = db.Column(db.String(100))
    chief_accounts_approved_at = db.Column(db.DateTime)
    total_net_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PayrollOTP(db.Model):
    __tablename__ = 'payroll_otps'
    
    id = db.Column(db.Integer, primary_key=True)
    otp_code = db.Column(db.String(10), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('payroll_batches.id'), nullable=False)
    requested_by = db.Column(db.String(100))
    approved_by = db.Column(db.String(100)) # MD
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    def is_valid(self):
        return not self.is_used and datetime.utcnow() < self.expires_at

class MDApprovalRequest(db.Model):
    __tablename__ = 'md_approval_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_name = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50), nullable=False) # 'Employees', 'Payroll', 'Payslip', 'Accounts'
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected
    otp_code = db.Column(db.String(10))
    request_time = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_used = db.Column(db.Boolean, default=False)

class AccessLog(db.Model):
    __tablename__ = 'access_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    personnel_name = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    time_in = db.Column(db.DateTime, default=datetime.utcnow)
    time_out = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

class PageAuthorization(db.Model):
    __tablename__ = 'page_authorizations'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    page_name = db.Column(db.String(100), nullable=False) # 'Employees', 'Payroll', 'Payslip', 'Accounts'
    secret_code = db.Column(db.String(4), nullable=True) # 4-digit secret code
    is_authorized = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    employee = db.relationship('Employee', backref=db.backref('authorizations', cascade='all, delete-orphan'))

# ==========================================
# ICT DEPARTMENT MODULE
# ==========================================

class ICTProject(db.Model):
    __tablename__ = 'ict_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=True)
    project_type = db.Column(db.String(100)) # Web App, Website, Software Update
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='Pending') # Pending, In Progress, Testing, Completed
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref='ict_projects')
    tasks = db.relationship('ICTTask', backref='project', lazy=True, cascade="all, delete-orphan")

class ICTDeveloper(db.Model):
    __tablename__ = 'ict_developers'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=False)
    skills = db.Column(db.String(200)) # Python, React, etc.
    projects_completed = db.Column(db.Integer, default=0)
    availability = db.Column(db.String(50), default='Available')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    employee = db.relationship('Employee', backref='ict_developer_profile')
    tasks = db.relationship('ICTTask', backref='developer', lazy=True)

class ICTTask(db.Model):
    __tablename__ = 'ict_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('ict_projects.id'), nullable=False)
    developer_id = db.Column(db.Integer, db.ForeignKey('ict_developers.id'), nullable=True)
    task_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='Pending') # Pending, In Progress, Testing, Completed
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ICTTraining(db.Model):
    __tablename__ = 'ict_trainings'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=True)
    training_name = db.Column(db.String(200), nullable=False)
    trainer_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'), nullable=True)
    schedule_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), default='Scheduled') # Scheduled, Completed, Cancelled
    training_fee = db.Column(db.Float, default=0.0)
    certificate_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref='ict_trainings')
    trainer = db.relationship('Employee', backref='ict_trainings_conducted')

class GeneralReceipt(db.Model):
    __tablename__ = 'general_receipts'
    
    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False)
    company = db.Column(db.String(100), nullable=False)
    tin = db.Column(db.String(50))
    receipt_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    received_from = db.Column(db.String(200), nullable=False)
    sum_of_words = db.Column(db.String(255), nullable=False)
    payment_for = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(100)) # Cash / Check No.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
