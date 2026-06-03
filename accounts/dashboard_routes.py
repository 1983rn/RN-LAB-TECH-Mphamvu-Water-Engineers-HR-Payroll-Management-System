from flask import Blueprint, render_template, request, flash, redirect, url_for, session, Response, make_response
from functools import wraps
from datetime import datetime, date
from models import (Inventory, FarmActivity, Transaction, Invoice, Quotation, Contract, 
                    FarmOutput, FarmExpense, Payroll, CashBookEntry, PayrollBatch, PayrollOTP, 
                    Employee, LodgeInventory, ConstructionStock, Livestock, FarmInput, LodgePayment, LodgeExpense)
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

@accounts_bp.before_request
def check_md_approval():
    # Only enforce when hitting actual accounts endpoints
    # MD (Director) bypasses this
    if session.get('role') == 'Director':
        return
        
    # Check if this user is in the ACL for 'Accounts'
    # We search by username/name logic. Since User and Employee aren't linked,
    # we'll check if any authorized Employee name matches the session username
    # or if there's an active authorization for the current requester name.
    # For consistency with the gateway, we check if they have a valid session token.
    # The gateway already checks the ACL during OTP request.
        
    if 'md_access_accounts' not in session or not session.get('md_access_accounts'):
        flash("Managing Director approval required to access the Accounts module.", "error")
        return redirect(url_for('hr.gateway', module='Accounts'))
        
    expiry_str = session.get('md_access_accounts_expiry')
    if not expiry_str or datetime.fromisoformat(expiry_str) < datetime.utcnow():
        session['md_access_accounts'] = False
        flash("Your MD approval token has expired. Please request a new OTP.", "warning")
        return redirect(url_for('hr.gateway', module='Accounts'))

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
    # 1. Total Inventory Wealth (Consolidated from all tables)
    # Generic Inventory (Borehole, ICT, HR, Accounts)
    standard_inventory_val = db.session.query(db.func.sum(Inventory.total_value)).filter(Inventory.condition != 'Poor').scalar() or 0
    # Lodge Inventory
    lodge_inventory_val = db.session.query(db.func.sum(LodgeInventory.total_value)).filter(LodgeInventory.condition != 'Poor').scalar() or 0
    # Construction Materials
    const_inventory_val = db.session.query(db.func.sum(ConstructionStock.total_value)).scalar() or 0
    # Farm Assets (Livestock + Inputs)
    livestock_val = db.session.query(db.func.sum(Livestock.purchase_price)).filter_by(status='Alive').scalar() or 0
    farm_inputs_val = db.session.query(db.func.sum(FarmInput.total_cost)).scalar() or 0
    
    total_inventory_wealth = standard_inventory_val + lodge_inventory_val + const_inventory_val + livestock_val + farm_inputs_val
    
    # 2. Consolidated Cashbook Totals (All 7 Departments)
    # Mapping the 7 departments as per company structure
    departments = [
        'Borehole Drilling', 
        'Farm', 
        'Construction', 
        'Lodge', 
        'ICT Department', 
        'HR', 
        'Accounts'
    ]
    dept_stats = []
    total_company_income = 0
    total_company_expense = 0

    for dept in departments:
        # a) Central Cashbook Entries
        income = db.session.query(db.func.sum(CashBookEntry.amount)).filter_by(department=dept, type='Credit').scalar() or 0
        expense = db.session.query(db.func.sum(CashBookEntry.amount)).filter_by(department=dept, type='Debit').scalar() or 0
        
        # b) Specialized Business Revenue (In case not mirrored in cashbook yet)
        if dept == 'Borehole Drilling':
            # Core transactions usually aren't all in cashbook yet
            income += db.session.query(db.func.sum(Transaction.amount)).filter_by(department='Borehole Drilling').scalar() or 0
        elif dept == 'Lodge':
            # LodgePayments aren't mirrored in cashbook in current logic
            income += db.session.query(db.func.sum(LodgePayment.amount)).filter_by(status='Completed').scalar() or 0
            expense += db.session.query(db.func.sum(LodgeExpense.amount)).scalar() or 0
        elif dept == 'Farm':
            # FarmExpenses might be separate from Cashbook
            expense += db.session.query(db.func.sum(FarmExpense.amount)).scalar() or 0
        
        # c) Staff Payroll (Company-wide staff costs)
        payroll_expense = db.session.query(db.func.sum(Payroll.net_salary)).join(Employee).filter(Employee.department == dept).scalar() or 0
        expense += payroll_expense
        
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
    departments = ['Borehole Drilling', 'Farm', 'Construction', 'Lodge', 'ICT Department', 'HR', 'Accounts']
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

@accounts_bp.route('/salaries/process-payment', methods=['POST'])
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

@accounts_bp.route('/salaries/lock-payroll', methods=['GET'])
@login_required
@accounts_required
def lock_payroll():
    accounts_name = session.get('accounts_processing_name')
    if accounts_name:
        from models import AccessLog
        active_logs = AccessLog.query.filter_by(personnel_name=accounts_name, module='Salary Payments', is_active=True).all()
        for log in active_logs:
            log.is_active = False
            log.time_out = datetime.utcnow()
        db.session.commit()
    
    session.pop('accounts_authorized', None)
    session.pop('accounts_processing_name', None)
    flash("Payroll securely locked.", "success")
    return redirect(url_for('accounts.salaries'))

@accounts_bp.route('/salaries/request-otp', methods=['POST'])
@login_required
@accounts_required
def request_otp():
    accounts_name = request.form.get('personnel_name')
    batch_id = request.form.get('batch_id')
    secret_code = request.form.get('secret_code', '').strip()
    
    if not accounts_name or not secret_code:
        flash("Please input your name and 4-digit secret code before requesting password.", "error")
        return redirect(url_for('accounts.salaries'))

    # MD Master Key bypass — the MD can use their authentication key to access any page
    MD_AUTH_KEY = "**//mweepDUWE."
    MD_NAME = "ULANDA DUWE"
    is_md = (secret_code == MD_AUTH_KEY and accounts_name.strip().upper() == MD_NAME)

    auth = None
    if not is_md:
        accounts_name_lower = accounts_name.lower()
        from models import PageAuthorization, Employee
        auth = PageAuthorization.query.join(Employee).filter(
            db.func.lower(Employee.first_name + ' ' + Employee.last_name) == accounts_name_lower,
            PageAuthorization.page_name == 'Salary_OTP',
            PageAuthorization.secret_code == secret_code,
            PageAuthorization.is_authorized == True
        ).first()
        
        if not auth and session.get('role') != 'Director':
            # Fallback: Check Python side in case DB concat lowercase fails
            all_auths = PageAuthorization.query.join(Employee).filter(
                PageAuthorization.page_name == 'Salary_OTP',
                PageAuthorization.secret_code == secret_code,
                PageAuthorization.is_authorized == True
            ).all()
            for a in all_auths:
                if f"{a.employee.first_name} {a.employee.last_name}".lower() == accounts_name_lower:
                    auth = a
                    break

        if not auth and session.get('role') != 'Director':
            flash(f"Unauthorized: Verification failed for '{accounts_name}'. Please check your name and 4-digit secret code.", "error")
            return redirect(url_for('accounts.salaries'))

    # Store processing session in session
    session['accounts_processing_name'] = accounts_name
    
    # Create an access log for Accounts Salary Payment
    from models import AccessLog
    active_logs = AccessLog.query.filter_by(personnel_name=accounts_name, module='Salary Payments', is_active=True).all()
    for log in active_logs:
        log.is_active = False
        log.time_out = datetime.utcnow()
        
    new_log = AccessLog(
        personnel_name=accounts_name,
        module='Salary Payments',
        is_active=True
    )
    db.session.add(new_log)
    db.session.commit()
    
    # Instantly grant authorization instead of OTP
    session['accounts_authorized'] = True
    flash("Authorization successful. Payroll unlocked.", "success")
        
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

@accounts_bp.route('/receipt', methods=['GET'])
@login_required
@accounts_required
def general_receipt():
    from models import GeneralReceipt
    
    # Auto-incrementing receipt number logic
    last_receipt = GeneralReceipt.query.order_by(GeneralReceipt.id.desc()).first()
    next_num = 1
    if last_receipt and last_receipt.receipt_number.isdigit():
        next_num = int(last_receipt.receipt_number) + 1
    next_receipt_number = f"{next_num:04d}"
    
    receipts_history = GeneralReceipt.query.order_by(GeneralReceipt.created_at.desc()).limit(50).all()
    
    return render_template('accounts/receipt.html', 
                           next_receipt_number=next_receipt_number, 
                           receipts_history=receipts_history)

@accounts_bp.route('/receipt/pdf', methods=['POST'])
@login_required
@accounts_required
def generate_general_receipt():
    from models import GeneralReceipt
    from utils.pdf_utils import generate_general_receipt_pdf
    
    company = request.form.get('company')
    tin = request.form.get('tin')
    receipt_number = request.form.get('receipt_number')
    date_str = request.form.get('date')
    received_from = request.form.get('received_from')
    sum_of_words = request.form.get('sum_of_words')
    payment_for = request.form.get('payment_for')
    amount_str = request.form.get('amount', '0').replace(',', '')
    payment_method = request.form.get('payment_method')
    
    try:
        amount = float(amount_str)
        receipt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Save to database
        receipt = GeneralReceipt(
            receipt_number=receipt_number,
            company=company,
            tin=tin,
            receipt_date=receipt_date,
            received_from=received_from,
            sum_of_words=sum_of_words,
            payment_for=payment_for,
            amount=amount,
            payment_method=payment_method
        )
        db.session.add(receipt)
        db.session.commit()
        
        # Generate PDF
        receipt_data = {
            'company': company,
            'tin': tin,
            'receipt_number': receipt_number,
            'date': receipt_date.strftime('%d/%m/%Y'),
            'received_from': received_from,
            'sum_of_words': sum_of_words,
            'payment_for': payment_for,
            'amount': amount,
            'payment_method': payment_method
        }
        
        buffer = generate_general_receipt_pdf(receipt_data)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=Receipt_{company.replace(" ", "_")}_{receipt_number}.pdf'
        return response
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating receipt: {str(e)}', 'error')
        return redirect(url_for('accounts.general_receipt'))
