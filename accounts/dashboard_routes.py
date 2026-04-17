from flask import Blueprint, render_template, request, flash, redirect, url_for, session, Response, make_response
from functools import wraps
from datetime import datetime, date
from models import Inventory, FarmActivity, Transaction, Invoice, Quotation, Contract, FarmOutput, FarmExpense, Payroll, CashBookEntry, PayrollBatch, PayrollOTP, Employee, LodgeInventory
from db_utils import db
import csv
import io
import random
import string
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from utils.pdf_utils import create_numbered_doc, add_company_header_to_story, build_pdf_with_numbering, add_pdf_footer

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def accounts_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['Administrator', 'Director', 'Accountant', 'Chief Accounts Personnel']:
            flash('You do not have permission to access the Accounts Department.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@accounts_bp.route('/', methods=['GET'])
@login_required
@accounts_required
def dashboard():
    # 1. Total Inventory Wealth (Excluding 'Poor' condition)
    # Generic Inventory
    standard_inventory_val = db.session.query(db.func.sum(Inventory.total_value)).filter(Inventory.condition != 'Poor').scalar() or 0
    # Lodge Inventory
    lodge_inventory_val = db.session.query(db.func.sum(LodgeInventory.total_value)).filter(LodgeInventory.condition != 'Poor').scalar() or 0
    total_inventory_wealth = standard_inventory_val + lodge_inventory_val
    
    # 2. Consolidated Cashbook Totals (All 7 Departments)
    departments = ['Borehole Drilling', 'Farm', 'Construction', 'Lodge', 'HR', 'Accounts', 'ICT Department']
    dept_stats = []
    total_company_income = 0
    total_company_expense = 0

    for dept in departments:
        income = db.session.query(db.func.sum(CashBookEntry.amount)).filter_by(department=dept, type='Credit').scalar() or 0
        expense = db.session.query(db.func.sum(CashBookEntry.amount)).filter_by(department=dept, type='Debit').scalar() or 0
        # Include specific transactions for business departments
        if dept == 'Borehole Drilling':
             income += db.session.query(db.func.sum(Transaction.amount)).filter_by(department='Borehole Drilling').scalar() or 0
        
        profit_loss = income - expense
        dept_stats.append({
            'name': dept,
            'income': income,
            'expense': expense,
            'net': profit_loss
        })
        total_company_income += income
        total_company_expense += expense

    # Ranking logic
    performance_ranking = sorted(dept_stats, key=lambda x: x['net'], reverse=True)
    
    # 3. Company Wealth
    total_cash_on_hand = total_company_income - total_company_expense
    company_wealth = total_cash_on_hand + total_inventory_wealth
    
    return render_template('accounts/dashboard.html',
                           dept_stats=dept_stats,
                           performance_ranking=performance_ranking,
                           total_company_income=total_company_income,
                           total_company_expense=total_company_expense,
                           total_inventory_wealth=total_inventory_wealth,
                           company_wealth=company_wealth,
                           datetime=datetime)

@accounts_bp.route('/salaries', methods=['GET', 'POST'])
@login_required
@accounts_required
def salaries():
    # Get active payroll batches
    batches = PayrollBatch.query.order_by(PayrollBatch.created_at.desc()).all()
    
    # Requirement: Categorize by departments
    departments = ['Borehole Drilling', 'Farm', 'Construction', 'Lodge', 'HR', 'Accounts', 'ICT Department']
    categorized_payroll = {}
    total_net_all = 0
    
    current_month = datetime.now().strftime('%Y-%m')
    for dept in departments:
        # Pull payroll items for this month grouped by dept
        records = Payroll.query.join(Employee).filter(
            Payroll.payroll_month == current_month,
            Employee.department == dept
        ).all()
        categorized_payroll[dept] = records
        total_net_all += sum(r.net_salary for r in records)

    return render_template('accounts/salaries.html', 
                           batches=batches, 
                           categorized_payroll=categorized_payroll,
                           current_month=current_month,
                           total_net_all=total_net_all)

@accounts_bp.route('/salaries/verify-otp', methods=['POST'])
@login_required
@accounts_required
def verify_otp():
    otp_code = request.form.get('otp_code')
    batch_id = request.form.get('batch_id', 1) # Fallback for now

    otp_record = PayrollOTP.query.filter_by(otp_code=otp_code, is_used=False).first()
    
    if otp_record and otp_record.is_valid():
        otp_record.is_used = True
        session['accounts_authorized'] = True
        db.session.commit()
        flash("Authorization successful. Payroll unlocked.", "success")
    else:
        flash("Invalid or expired OTP. Please request another one.", "error")
        
    return redirect(url_for('accounts.salaries'))

@accounts_bp.route('/salaries/process-payment', methods=['POST'])
@login_required
@accounts_required
def process_payment():
    if not session.get('accounts_authorized'):
        flash("Security authorization required.", "error")
        return redirect(url_for('accounts.salaries'))

    payroll_id = request.form.get('payroll_id')
    method = request.form.get('method')
    
    payroll = Payroll.query.get_or_404(payroll_id)
    
    # Simulated API Gateway
    api_response = {
        'status': 'Pending',
        'ref': f'PAY-{method[:3].upper()}-{datetime.now().strftime("%y%m%d%H%M%S")}'
    }
    
    # Mocking different channel behaviors
    if method == 'Bank':
        # Bank Transfer Simulation
        api_response['status'] = 'Success'
        api_response['message'] = 'EFT Transfer Initiated'
    elif method == 'Airtel Money':
        # Mobile Money API Simulation
        api_response['status'] = 'Success'
        api_response['message'] = 'Push Notification Sent to Subscriber'
    elif method == 'Mpamba':
        # TNM Mpamba API Simulation
        api_response['status'] = 'Success'
        api_response['message'] = 'Wallet Disbursement Confirmed'
    
    if api_response['status'] == 'Success':
        payroll.status = f'Paid via {method}'
        payroll.payment_ref = api_response['ref']
        db.session.commit()
        flash(f"{api_response['message']}. Amount: MWK {payroll.net_salary:,.2f}. Ref: {api_response['ref']}", "success")
    else:
        flash(f"API Gateway Error ({method}): Service temporarily unavailable.", "error")
    
    return redirect(url_for('accounts.salaries'))

@accounts_bp.route('/salaries/request-otp', methods=['POST'])
@login_required
@accounts_required
def request_otp():
    accounts_name = request.form.get('personnel_name')
    batch_id = request.form.get('batch_id')
    
    if not accounts_name:
        flash("Please input your name before requesting password.", "error")
        return redirect(url_for('accounts.salaries'))

    # Store processing session in session
    session['accounts_processing_name'] = accounts_name
    
    # Check if a request already exists
    existing_otp = PayrollOTP.query.filter_by(batch_id=batch_id, is_used=False).first()
    if existing_otp and existing_otp.is_valid():
        flash("A password request is already pending or valid.", "info")
    else:
        # Create OTP Request (MD will see this in their portal)
        # For now, we simulate the MD generating it
        flash("Password request sent to MD. Please wait for approval.", "success")
        
    return redirect(url_for('accounts.salaries'))

@accounts_bp.route('/md/approve-payroll-otp', methods=['POST'])
@login_required # Should be MD role check
def md_approve_otp():
    if session.get('role') != 'Director':
        flash("Only the Managing Director can generate payroll OTPs.", "error")
        return redirect(url_for('dashboard'))
    
    batch_id = request.form.get('batch_id')
    
    # Generate random 6-digit OTP
    otp_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # OTP Expiration strictly 2 hours and 30 minutes (150 minutes)
    expires_at = datetime.utcnow() + datetime.timedelta(minutes=150)
    
    new_otp = PayrollOTP(
        otp_code=otp_code,
        batch_id=batch_id,
        requested_by="Accounts Department",
        approved_by=session.get('username'),
        expires_at=expires_at
    )
    db.session.add(new_otp)
    db.session.commit()
    
    # Requirement: MD should see the code to send manually
    flash(f"OTP GENERATED: {otp_code}. Please send this to Accounts via WhatsApp/SMS/Email. Valid for 2.5 hours.", "success")
    return redirect(request.referrer)

@accounts_bp.route('/cashbook', methods=['GET'])
@login_required
@accounts_required
def cashbook():
    # Credits
    transactions = Transaction.query.all()
    farm_outputs = FarmOutput.query.all()
    manual_credits = CashBookEntry.query.filter_by(type='Credit').all()
    
    # Debits
    farm_expenses = FarmExpense.query.all()
    payrolls = Payroll.query.all()
    manual_debits = CashBookEntry.query.filter_by(type='Debit').all()
    
    # Merge and format
    credits_list = []
    for t in transactions:
        credits_list.append({
            'date': t.payment_date,
            'description': t.notes or f"Business Transaction - {t.client.client_name if t.client else ''}",
            'ref': t.reference_number,
            'amount': float(t.amount) if t.amount else 0.0,
            'category': t.department if t.department else 'Core Business'
        })
    for fo in farm_outputs:
        credits_list.append({
            'date': fo.date_added.date() if isinstance(fo.date_added, datetime) else fo.date_added,
            'description': fo.product_name,
            'ref': "FARM-OUT",
            'amount': float(fo.total_value) if fo.total_value else 0.0,
            'category': 'Farm Operations'
        })
    for mc in manual_credits:
        credits_list.append({
            'date': mc.date,
            'description': mc.description,
            'ref': mc.reference or "MANUAL",
            'amount': float(mc.amount) if mc.amount else 0.0,
            'category': mc.category or 'Manual Entry'
        })
        
    debits_list = []
    for fe in farm_expenses:
        debits_list.append({
            'date': fe.expense_date,
            'description': fe.description or fe.expense_category,
            'ref': "FARM-EXP",
            'amount': float(fe.amount) if fe.amount else 0.0,
            'category': fe.expense_category or 'Farm Expense'
        })
    for p in payrolls:
        debits_list.append({
            'date': p.created_at.date() if isinstance(p.created_at, datetime) else p.created_at,
            'description': f"Staff Salary - {p.payroll_month} ({p.employee.first_name if p.employee else ''})",
            'ref': p.reference_number,
            'amount': float(p.net_salary) if p.net_salary else 0.0,
            'category': 'Staff Costs'
        })
    for md in manual_debits:
        debits_list.append({
            'date': md.date,
            'description': md.description,
            'ref': md.reference or "MANUAL",
            'amount': float(md.amount) if md.amount else 0.0,
            'category': md.category or 'Manual Entry'
        })
        
    # Sort by date desc
    credits_list.sort(key=lambda x: x['date'] if x['date'] else datetime.min.date(), reverse=True)
    debits_list.sort(key=lambda x: x['date'] if x['date'] else datetime.min.date(), reverse=True)
    
    # Calculate Opening Balance (Look for a "Opening Balance" entry in manual credits)
    opening_balance_entry = CashBookEntry.query.filter(CashBookEntry.description.ilike('%Opening Balance%')).first()
    opening_balance = float(opening_balance_entry.amount) if opening_balance_entry else 0.0
    
    # Calculate Total Inventory Asset Value
    total_inventory = db.session.query(db.func.sum(Inventory.total_value)).scalar() or 0.0
    
    # Calculate totals
    total_income = sum(c['amount'] for c in credits_list if "Opening Balance" not in c['description'])
    total_debits = sum(d['amount'] for d in debits_list)
    balance = opening_balance + total_income - total_debits
    
    # Income Breakdown
    income_breakdown = {}
    for c in credits_list:
        if "Opening Balance" in c['description']: continue
        cat = c['category']
        income_breakdown[cat] = income_breakdown.get(cat, 0.0) + c['amount']
    
    # Expense Breakdown
    expense_breakdown = {}
    for d in debits_list:
        cat = d['category']
        expense_breakdown[cat] = expense_breakdown.get(cat, 0.0) + d['amount']

    return render_template('accounts/cashbook.html',
                           credits=credits_list,
                           debits=debits_list,
                           opening_balance=opening_balance,
                           total_income=total_income,
                           total_debits=total_debits,
                           balance=balance,
                           income_breakdown=income_breakdown,
                           expense_breakdown=expense_breakdown,
                           total_inventory=total_inventory,
                           now=datetime.now())

@accounts_bp.route('/cashbook/add', methods=['POST'])
@login_required
@accounts_required
def add_cashbook_entry():
    try:
        # Using .get() for robustness
        date_str = request.form.get('date')
        description = request.form.get('description')
        amount_str = request.form.get('amount')
        entry_type = request.form.get('type')
        
        # Explicit validation for required fields
        if not all([date_str, description, amount_str, entry_type]):
            missing = [k for k in ['date', 'description', 'amount', 'type'] if not request.form.get(k)]
            flash(f"Error adding entry: Missing required fields: {', '.join(missing)}", 'error')
            return redirect(url_for('accounts.cashbook'))

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        amount = float(amount_str)
        reference = request.form.get('reference')
        category = request.form.get('category')
        department = request.form.get('department')
        
        entry = CashBookEntry(
            date=date_obj,
            description=description,
            reference=reference,
            amount=amount,
            type=entry_type,
            category=category,
            department=department
        )
        db.session.add(entry)
        db.session.commit()
        flash('Entry added to Cash Book successfully!', 'success')
    except ValueError:
        flash('Error adding entry: Invalid date or amount format.', 'error')
    except Exception as e:
        flash(f'Error adding entry: {str(e)}', 'error')
    
    return redirect(url_for('accounts.cashbook'))

@accounts_bp.route('/analysis', methods=['GET'])
@login_required
@accounts_required
def analysis():
    period = request.args.get('period', 'monthly') # monthly, mid-year, annual
    
    month_str = request.args.get('month')
    year_str = request.args.get('year')
    month = int(month_str) if month_str and month_str.isdigit() else datetime.now().month
    year = int(year_str) if year_str and year_str.isdigit() else datetime.now().year
    
    # Define date filters based on period
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date()
    else:
        end_date = datetime(year, month + 1, 1).date()
        
    if period == 'mid-year':
        if month <= 6:
            start_date = datetime(year, 1, 1).date()
            end_date = datetime(year, 7, 1).date()
        else:
            start_date = datetime(year, 7, 1).date()
            end_date = datetime(year + 1, 1, 1).date()
    elif period == 'annual':
        start_date = datetime(year, 1, 1).date()
        end_date = datetime(year + 1, 1, 1).date()

    # Data Fetching
    transactions = Transaction.query.filter(Transaction.payment_date >= start_date, Transaction.payment_date < end_date).all()
    farm_outputs = FarmOutput.query.filter(FarmOutput.date_added >= datetime.combine(start_date, datetime.min.time()), FarmOutput.date_added < datetime.combine(end_date, datetime.min.time())).all()
    farm_expenses = FarmExpense.query.filter(FarmExpense.expense_date >= start_date, FarmExpense.expense_date < end_date).all()
    payrolls = Payroll.query.filter(Payroll.created_at >= datetime.combine(start_date, datetime.min.time()), Payroll.created_at < datetime.combine(end_date, datetime.min.time())).all()
    cashbook_entries = CashBookEntry.query.filter(CashBookEntry.date >= start_date, CashBookEntry.date < end_date).all()

    # Departmental Aggregation
    dept_data = {} # { 'Dept Name': {'income': 0, 'expense': 0, 'net': 0} }

    def add_to_dept(dept, amount, is_income=True):
        if not dept: dept = "Uncategorized"
        if dept not in dept_data:
            dept_data[dept] = {'income': 0.0, 'expense': 0.0, 'net': 0.0}
            
        safe_amount = float(amount) if amount is not None else 0.0
        if is_income:
            dept_data[dept]['income'] += safe_amount
        else:
            dept_data[dept]['expense'] += safe_amount
        dept_data[dept]['net'] = dept_data[dept]['income'] - dept_data[dept]['expense']

    # 1. Core Business
    for t in transactions:
        add_to_dept("Core Business", t.amount, True)
    
    # 2. Farm Operations
    for fo in farm_outputs:
        add_to_dept("Farm Operations", fo.total_value, True)
    for fe in farm_expenses:
        add_to_dept("Farm Operations", fe.amount, False)
        
    # 3. Staff Costs (by Employee Department)
    for p in payrolls:
        dept = p.employee.department if p.employee else "Staff Costs"
        add_to_dept(dept, p.net_salary, False)
        
    # 4. Manual Cashbook Entries
    for ce in cashbook_entries:
        if ce.type == 'Credit':
            add_to_dept(ce.department or ce.category or "General", ce.amount, True)
        else:
            add_to_dept(ce.department or ce.category or "General", ce.amount, False)

    # Convert to list and sort for ranking
    rank_list = []
    for dept, data in dept_data.items():
        rank_list.append({
            'name': dept,
            'income': data['income'],
            'expense': data['expense'],
            'net': data['net']
        })

    # Rankings
    income_ranking = sorted(rank_list, key=lambda x: x['income'], reverse=True)
    expense_ranking = sorted(rank_list, key=lambda x: x['expense'], reverse=True)
    performance_ranking = sorted(rank_list, key=lambda x: x['net'], reverse=True)

    return render_template('accounts/analysis.html',
                           period=period,
                           month=month,
                           year=year,
                           income_ranking=income_ranking,
                           expense_ranking=expense_ranking,
                           performance_ranking=performance_ranking,
                           dept_data=dept_data,
                           now=datetime.now())

@accounts_bp.route('/cashbook/export', methods=['GET'])
@login_required
@accounts_required
def export_cashbook():
    # Credits
    transactions = Transaction.query.all()
    farm_outputs = FarmOutput.query.all()
    manual_credits = CashBookEntry.query.filter_by(type='Credit').all()
    
    # Debits
    farm_expenses = FarmExpense.query.all()
    payrolls = Payroll.query.all()
    manual_debits = CashBookEntry.query.filter_by(type='Debit').all()
    
    entries = []
    
    for t in transactions:
        entries.append([t.payment_date, f"Business Transaction - {t.client.client_name if t.client else ''}", t.reference_number, 'Credit', float(t.amount) if t.amount else 0.0, 'Core Business'])
    for fo in farm_outputs:
        entries.append([fo.date_added.date() if isinstance(fo.date_added, datetime) else fo.date_added, fo.product_name, "FARM-OUT", 'Credit', float(fo.total_value) if fo.total_value else 0.0, 'Farm Operations'])
    for mc in manual_credits:
        entries.append([mc.date, mc.description, mc.reference or "MANUAL", 'Credit', float(mc.amount) if mc.amount else 0.0, mc.category or 'Manual Entry'])
        
    for fe in farm_expenses:
        entries.append([fe.expense_date, fe.description or fe.expense_category, "FARM-EXP", 'Debit', float(fe.amount) if fe.amount else 0.0, fe.expense_category or 'Farm Expense'])
    for p in payrolls:
        entries.append([p.created_at.date() if isinstance(p.created_at, datetime) else p.created_at, f"Staff Salary - {p.payroll_month} ({p.employee.first_name if p.employee else ''})", p.reference_number, 'Debit', float(p.net_salary) if p.net_salary else 0.0, 'Staff Costs'])
    for md in manual_debits:
        entries.append([md.date, md.description, md.reference or "MANUAL", 'Debit', float(md.amount) if md.amount else 0.0, md.category or 'Manual Entry'])
        
    entries.sort(key=lambda x: x[0] if x[0] else datetime.min.date(), reverse=True)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Description', 'Reference', 'Type', 'Amount (MWK)', 'Category'])
    
    for e in entries:
        writer.writerow([e[0], e[1], e[2], e[3], "{:.2f}".format(e[4]), e[5]])
        
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=cashbook_export.csv"}
    )

@accounts_bp.route('/cashbook/pdf', methods=['GET'])
@login_required
@accounts_required
def export_cashbook_pdf():
    # 1. Data Collection
    transactions = Transaction.query.all()
    farm_outputs = FarmOutput.query.all()
    manual_credits = CashBookEntry.query.filter_by(type='Credit').all()
    
    farm_expenses = FarmExpense.query.all()
    payrolls = Payroll.query.all()
    manual_debits = CashBookEntry.query.filter_by(type='Debit').all()
    
    credits_list = []
    for t in transactions:
        credits_list.append({
            'date': t.payment_date,
            'description': t.notes or f"Business Transaction - {t.client.client_name if t.client else ''}",
            'ref': t.reference_number,
            'amount': float(t.amount) if t.amount else 0.0
        })
    for fo in farm_outputs:
        credits_list.append({
            'date': fo.date_added.date() if isinstance(fo.date_added, datetime) else fo.date_added,
            'description': fo.product_name,
            'ref': "FARM-OUT",
            'amount': float(fo.total_value) if fo.total_value else 0.0
        })
    for mc in manual_credits:
        credits_list.append({
            'date': mc.date,
            'description': mc.description,
            'ref': mc.reference or "MANUAL",
            'amount': float(mc.amount) if mc.amount else 0.0
        })
        
    debits_list = []
    for fe in farm_expenses:
        debits_list.append({
            'date': fe.expense_date,
            'description': fe.description or fe.expense_category,
            'ref': "FARM-EXP",
            'amount': float(fe.amount) if fe.amount else 0.0
        })
    for p in payrolls:
        debits_list.append({
            'date': p.created_at.date() if isinstance(p.created_at, datetime) else p.created_at,
            'description': f"Staff Salary - {p.payroll_month} ({p.employee.first_name if p.employee else ''})",
            'ref': p.reference_number,
            'amount': float(p.net_salary) if p.net_salary else 0.0
        })
    for md in manual_debits:
        debits_list.append({
            'date': md.date,
            'description': md.description,
            'ref': md.reference or "MANUAL",
            'amount': float(md.amount) if md.amount else 0.0
        })
        
    # Sort
    credits_list.sort(key=lambda x: x['date'] if x['date'] else date.min, reverse=True)
    debits_list.sort(key=lambda x: x['date'] if x['date'] else date.min, reverse=True)
    
    # Financials
    opening_balance_entry = CashBookEntry.query.filter(CashBookEntry.description.ilike('%Opening Balance%')).first()
    opening_balance = float(opening_balance_entry.amount) if opening_balance_entry else 0.0
    total_income = sum(c['amount'] for c in credits_list if "Opening Balance" not in c['description'])
    total_debits = sum(d['amount'] for d in debits_list)
    balance = opening_balance + total_income - total_debits

    # 2. PDF Generation
    buffer = io.BytesIO()
    doc = create_numbered_doc(buffer, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    # Header
    story = add_company_header_to_story(story, layout_mode='dense', department='Accounts Department')
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=10)
    story.append(Paragraph("CASH BOOK LEDGER", title_style))
    story.append(Paragraph(f"Financial Period: Up to {datetime.now().strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Summary Table
    summary_data = [
        [Paragraph("<b>OPENING BALANCE</b>", styles['Normal']), f"MWK {opening_balance:,.2f}"],
        [Paragraph("<b>TOTAL CREDITS (+)</b>", styles['Normal']), f"MWK {total_income:,.2f}"],
        [Paragraph("<b>TOTAL DEBITS (-)</b>", styles['Normal']), f"MWK {total_debits:,.2f}"],
        [Paragraph("<b>CLOSING BALANCE</b>", styles['Normal']), f"MWK {balance:,.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BACKGROUND', (0,3), (1,3), colors.lightgrey),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 25))
    
    # 3. Two-Column Ledger Layout
    # Left Side: Credits (Income)
    credits_header = [['Date', 'Description', 'Ref', 'Amount']]
    credits_data = credits_header + [[
        c['date'].strftime('%d/%m/%Y') if c['date'] else '',
        Paragraph(c['description'], styles['Normal']),
        c['ref'],
        f"{c['amount']:,.2f}"
    ] for c in credits_list]
    
    if opening_balance > 0:
        credits_data.insert(1, ['01/01/2026', 'Opening Balance b/f', 'OPEN-BAL', f"{opening_balance:,.2f}"])

    # Right Side: Debits (Payments)
    debits_header = [['Date', 'Description', 'Ref', 'Amount']]
    debits_data = debits_header + [[
        d['date'].strftime('%d/%m/%Y') if d['date'] else '',
        Paragraph(d['description'], styles['Normal']),
        d['ref'],
        f"{d['amount']:,.2f}"
    ] for d in debits_list]
    
    # Create the two sub-tables
    col_widths = [65, 160, 60, 85] 
    
    t_credits = Table(credits_data, colWidths=col_widths, repeatRows=1)
    t_credits.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    
    t_debits = Table(debits_data, colWidths=col_widths, repeatRows=1)
    t_debits.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkred),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    
    # Wrapper table to place them side-by-side
    side_by_side = Table([
        [Paragraph("<b>CREDITS (Income / Receipts)</b>", styles['Normal']), Paragraph("<b>DEBITS (Payments / Expenditure)</b>", styles['Normal'])],
        [t_credits, t_debits]
    ], colWidths=[385, 385])
    side_by_side.setStyle(TableStyle([
        ('VALIGN', (0,1), (-1,1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    
    story.append(side_by_side)
    
    # Footer
    story = add_pdf_footer(story)
    
    build_pdf_with_numbering(doc, story)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=CashBook_Ledger_Mphamvu.pdf'
    return response

