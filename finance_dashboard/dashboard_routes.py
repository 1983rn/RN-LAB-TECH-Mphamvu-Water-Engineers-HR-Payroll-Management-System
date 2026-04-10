from flask import Blueprint, render_template, request, flash, redirect, url_for, session, Response, make_response
from functools import wraps
from datetime import datetime, date
from models import Inventory, FarmActivity, Transaction, Invoice, Quotation, Contract, FarmOutput, FarmExpense, Payroll, CashBookEntry
from db_utils import db
import csv
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from utils.pdf_utils import create_numbered_doc, add_company_header_to_story, build_pdf_with_numbering, add_pdf_footer

finance_dashboard_bp = Blueprint('finance_dashboard', __name__, url_prefix='/financial-dashboard')

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
        if session.get('role') not in ['Administrator', 'Director', 'Accountant']:
            flash('You do not have permission to access the Financial Dashboard.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@finance_dashboard_bp.route('/', methods=['GET'])
@login_required
@admin_required
def dashboard():
    # 1. Total Inventory Value
    total_inventory = db.session.query(db.func.sum(Inventory.total_value)).scalar() or 0
    
    # 2. Total Business Income (from closed Invoices or Transactions)
    # We will use sum of Transactions for actual cash collected, and Invoices for Billed
    total_billed = db.session.query(db.func.sum(Invoice.amount)).scalar() or 0
    total_collected = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0
    
    # 3. Farm Income and Expenses
    activities = FarmActivity.query.all()
    farm_income = sum(output.total_value for activity in activities for output in activity.outputs)
    farm_expenses = sum(expense.amount for activity in activities for expense in activity.expenses)
    net_farm_profit = farm_income - farm_expenses
    
    # 4. Total Company Value
    # Assets (Inventory) + Cash Collected + Net Farm Profit (assuming cash reinvested/retained)
    # This is a simplified metric requested
    total_company_value = total_inventory + total_collected + net_farm_profit
    
    return render_template('finance_dashboard/dashboard.html',
                           total_inventory=total_inventory,
                           total_billed=total_billed,
                           total_collected=total_collected,
                           farm_income=farm_income,
                           farm_expenses=farm_expenses,
                           net_farm_profit=net_farm_profit,
                           total_company_value=total_company_value)

@finance_dashboard_bp.route('/cashbook', methods=['GET'])
@login_required
@admin_required
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
            'category': 'Core Business'
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

    return render_template('finance_dashboard/cashbook.html',
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

@finance_dashboard_bp.route('/cashbook/add', methods=['POST'])
@login_required
@admin_required
def add_cashbook_entry():
    try:
        date_str = request.form['date']
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        description = request.form['description']
        reference = request.form.get('reference')
        amount = float(request.form['amount'])
        entry_type = request.form['type']
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
    except Exception as e:
        flash(f'Error adding entry: {str(e)}', 'error')
    
    return redirect(url_for('finance_dashboard.cashbook'))

@finance_dashboard_bp.route('/analysis', methods=['GET'])
@login_required
@admin_required
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

    return render_template('finance_dashboard/analysis.html',
                           period=period,
                           month=month,
                           year=year,
                           income_ranking=income_ranking,
                           expense_ranking=expense_ranking,
                           performance_ranking=performance_ranking,
                           dept_data=dept_data,
                           now=datetime.now())

@finance_dashboard_bp.route('/cashbook/export', methods=['GET'])
@login_required
@admin_required
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

@finance_dashboard_bp.route('/cashbook/pdf', methods=['GET'])
@login_required
@admin_required
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
    story = add_company_header_to_story(story, layout_mode='dense')
    
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

