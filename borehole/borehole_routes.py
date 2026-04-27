from flask import Blueprint, render_template, session, redirect, url_for, request
from functools import wraps
from models import Quotation, Inventory, CashBookEntry, Client, Invoice, DeliveryNote, Transaction
from utils.auth_utils import apply_dept_filter
from db_utils import db
from datetime import datetime, timedelta

borehole_bp = Blueprint('borehole', __name__, url_prefix='/borehole')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@borehole_bp.route('/')
@login_required
def dashboard():
    # Set the department context in session for dynamic sidebar
    session['department_context'] = 'Borehole Drilling'
    session['department_dashboard'] = 'borehole.dashboard'
    return render_template('borehole/dashboard.html')

@borehole_bp.route('/quotations')
@login_required
def list_quotations():
    query = apply_dept_filter(Quotation.query, Quotation)
    quotations = query.order_by(Quotation.created_at.desc()).all()
    return render_template('quotations/list.html', quotations=quotations, is_borehole=True, timedelta=timedelta)

@borehole_bp.route('/inventory')
@login_required
def list_inventory():
    query = apply_dept_filter(Inventory.query, Inventory)
    items = query.all()
    
    # Calculate totals and categories for the template summary
    grand_total = sum((item.total_value or 0.0) for item in items)
    categories = {}
    for item in items:
        # Use subcategory for the breakdown if provided, otherwise category
        cat_name = item.subcategory if item.subcategory else item.category
        if cat_name not in categories:
            categories[cat_name] = {'count': 0, 'total_value': 0}
        categories[cat_name]['count'] += (item.quantity or 0)
        categories[cat_name]['total_value'] += (item.total_value or 0.0)

    return render_template('inventory/list.html', 
                           items=items, 
                           grand_total=grand_total,
                           categories=categories,
                           is_borehole=True)

@borehole_bp.route('/cashbook')
@login_required
def cashbook():
    # 1. Get Manual CashBook Entries
    entries_query = apply_dept_filter(CashBookEntry.query, CashBookEntry)
    entries = entries_query.order_by(CashBookEntry.date.desc()).all()
    
    # 2. Get Business Transactions (Client Payments)
    tx_query = apply_dept_filter(Transaction.query, Transaction)
    transactions = tx_query.all()
    
    # Format entries for the common cashbook template
    credits_list = []
    debits_list = []
    
    # Process Transactions (All are Credits in cashbook context)
    for t in transactions:
        credits_list.append({
            'date': t.payment_date,
            'description': t.notes or f"Client Payment - {t.client.client_name if t.client else 'Unknown'}",
            'ref': t.reference_number,
            'amount': float(t.amount) if t.amount else 0.0,
            'category': 'Business Revenue',
            'department': 'Borehole Drilling'
        })
        
    # Process Manual Entries
    for e in entries:
        item = {
            'date': e.date,
            'description': e.description,
            'ref': e.reference or 'Borehole',
            'amount': float(e.amount) if e.amount else 0.0,
            'category': e.category or 'Operations',
            'department': e.department
        }
        if e.type == 'Credit':
            credits_list.append(item)
        else:
            debits_list.append(item)
            
    # Calculate Opening Balance for this department
    opening_balance_entry = CashBookEntry.query.filter(
        CashBookEntry.department == 'Borehole Drilling',
        CashBookEntry.description.ilike('%Opening Balance%')
    ).first()
    opening_balance = float(opening_balance_entry.amount) if opening_balance_entry else 0.0
    
    # Calculate Total Inventory Asset Value for this department
    total_inventory = db.session.query(db.func.sum(Inventory.total_value)).filter(apply_dept_filter(Inventory.query, Inventory).where_clause).scalar() or 0.0
    
    # Calculate totals
    # Filter out opening balance from income sum to avoid double counting
    total_income = sum((c['amount'] or 0.0) for c in credits_list if "Opening Balance" not in c['description'])
    total_debits = sum((d['amount'] or 0.0) for d in debits_list)
    balance = opening_balance + total_income - total_debits
    
    # Breakdowns
    income_breakdown = {}
    for c in credits_list:
        if "Opening Balance" in c['description']: continue
        cat = c['category']
        income_breakdown[cat] = income_breakdown.get(cat, 0) + c['amount']
        
    expense_breakdown = {}
    for d in debits_list:
        cat = d['category']
        expense_breakdown[cat] = expense_breakdown.get(cat, 0) + d['amount']
    
    # Sort lists by date
    credits_list.sort(key=lambda x: x['date'], reverse=True)
    debits_list.sort(key=lambda x: x['date'], reverse=True)

    return render_template('finance_dashboard/cashbook.html', 
                           credits=credits_list,
                           debits=debits_list,
                           total_income=total_income,
                           total_debits=total_debits,
                           balance=balance,
                           opening_balance=opening_balance,
                           total_inventory=total_inventory,
                           income_breakdown=income_breakdown,
                           expense_breakdown=expense_breakdown,
                           now=datetime.now(),
                           is_borehole=True)

@borehole_bp.route('/exit')
@login_required
def exit_department():
    session.pop('department_context', None)
    return redirect(url_for('dashboard'))
