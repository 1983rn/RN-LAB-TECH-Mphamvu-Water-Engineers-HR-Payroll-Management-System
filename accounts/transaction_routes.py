from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Transaction, Client, Invoice
from datetime import datetime, date
from functools import wraps
from utils.credit_scoring import update_client_credit_score
from utils.auth_utils import apply_dept_filter, get_current_dept

transaction_bp = Blueprint('transactions', __name__, url_prefix='/accounts/transactions')

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
        if session.get('role') not in ['Administrator', 'HR Manager']:
            flash('Administrator access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@transaction_bp.route('/')
@login_required
@admin_required
def transaction_list():
    # Get filter parameters
    client_id = request.args.get('client_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')
    
    # Build query
    query = Transaction.query
    query = apply_dept_filter(query, Transaction)
    
    if client_id:
        query = query.filter(Transaction.client_id == client_id)
    if start_date:
        query = query.filter(Transaction.payment_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Transaction.payment_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    if status:
        query = query.filter(Transaction.status == status)
    
    transactions = query.order_by(Transaction.payment_date.desc()).all()
    
    # Get clients for filter dropdown
    c_query = Client.query
    clients = apply_dept_filter(c_query, Client).all()
    
    return render_template('accounts/transactions/list.html',
                         transactions=transactions,
                         clients=clients,
                         client_id=client_id,
                         start_date=start_date,
                         end_date=end_date,
                         status=status)

@transaction_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_transaction():
    if request.method == 'POST':
        try:
            client_id = request.form['client_id']
            invoice_id = request.form.get('invoice_id')
            amount = float(request.form['amount'])
            payment_method = request.form['payment_method']
            payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
            transaction_reference = request.form.get('transaction_reference')
            bank_account = request.form.get('bank_account')
            notes = request.form.get('notes')
            
            # Get department from invoice if linked
            dept = 'Borehole Drilling'
            if invoice_id:
                invoice = Invoice.query.get(invoice_id)
                if invoice:
                    dept = invoice.department
                    invoice.paid_amount += amount
                    if invoice.paid_amount >= invoice.amount:
                        invoice.status = 'Paid'
                    else:
                        invoice.status = 'Partially Paid'
                    
                    # Update client payment status
                    invoice.contract.quotation.client.payment_status = 'Partially Paid'
            elif session.get('department_context'):
                dept = session.get('department_context')

            transaction = Transaction(
                client_id=client_id,
                invoice_id=invoice_id if invoice_id else None,
                amount=amount,
                payment_method=payment_method,
                payment_date=payment_date,
                transaction_reference=transaction_reference,
                bank_account=bank_account,
                notes=notes,
                status='Completed',
                department=dept or get_current_dept()
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            # Auto-update the credit score after payment is recorded
            update_client_credit_score(client_id)
            
            flash('Transaction recorded successfully!', 'success')
            return redirect(url_for('transactions.transaction_list'))
            
        except Exception as e:
            flash(f'Error adding transaction: {str(e)}', 'error')
            return redirect(url_for('transactions.add_transaction'))
    
    # Get clients and invoices for dropdowns
    c_query = Client.query
    clients = apply_dept_filter(c_query, Client).all()
    i_query = Invoice.query.filter(Invoice.status.in_(['Unpaid', 'Partially Paid']))
    invoices = apply_dept_filter(i_query, Invoice).all()
    
    return render_template('finance/transactions/add.html',
                         clients=clients,
                         invoices=invoices)

@transaction_bp.route('/edit/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    
    if request.method == 'POST':
        try:
            # Update transaction details
            transaction.amount = float(request.form['amount'])
            transaction.payment_method = request.form['payment_method']
            transaction.payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
            transaction.transaction_reference = request.form.get('transaction_reference')
            transaction.bank_account = request.form.get('bank_account')
            transaction.notes = request.form.get('notes')
            transaction.status = request.form.get('status', 'Completed')
            
            db.session.commit()
            
            # Auto-update the credit score after payment is recorded
            update_client_credit_score(transaction.client_id)
            
            flash('Transaction updated successfully!', 'success')
            return redirect(url_for('transactions.transaction_list'))
            
        except Exception as e:
            flash(f'Error updating transaction: {str(e)}', 'error')
            return redirect(url_for('transactions.edit_transaction', transaction_id=transaction_id))
    
    c_query = Client.query
    clients = apply_dept_filter(c_query, Client).all()
    return render_template('finance/transactions/edit.html',
                         transaction=transaction,
                         clients=clients)

@transaction_bp.route('/delete/<int:transaction_id>', methods=['POST'])
@login_required
@admin_required
def delete_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    
    try:
        # Update invoice paid amount if invoice is linked
        invoice = None
        if transaction.invoice_id:
            invoice = Invoice.query.get(transaction.invoice_id)
            if invoice:
                invoice.paid_amount -= transaction.amount
                if invoice.paid_amount <= 0:
                    invoice.status = 'Unpaid'
                    invoice.paid_amount = 0
                else:
                    invoice.status = 'Partially Paid'
        
        client_id_to_update = transaction.client_id
        
        db.session.delete(transaction)
        db.session.commit()
        
        # Update credit score automatically
        update_client_credit_score(client_id_to_update)

        flash('Payment deleted successfully.', 'success')
        return redirect(url_for('transactions.transaction_list'))
        
    except Exception as e:
        flash(f'Error deleting transaction: {str(e)}', 'error')
        return redirect(url_for('transactions.transaction_list'))

@transaction_bp.route('/dashboard')
@login_required
@admin_required
def transaction_dashboard():
    # Get transaction statistics
    q = apply_dept_filter(Transaction.query, Transaction)
    total_transactions = q.count()
    total_amount = db.session.query(db.func.sum(Transaction.amount)).filter(apply_dept_filter(Transaction.query, Transaction).where_clause).scalar() or 0
    # Wait, the above total_amount query is complex with filter. 
    # Let me simplify:
    transactions = q.all()
    total_amount = sum(t.amount for t in transactions)
    
    # Get current month transactions
    current_month = date.today().replace(day=1)
    monthly_txs = [t for t in transactions if t.payment_date >= current_month]
    monthly_transactions = len(monthly_txs)
    monthly_amount = sum(t.amount for t in monthly_txs)
    
    # Get payment method breakdown
    payment_methods_dict = {}
    for t in transactions:
        pm = t.payment_method
        if pm not in payment_methods_dict:
            payment_methods_dict[pm] = {'count': 0, 'total': 0}
        payment_methods_dict[pm]['count'] += 1
        payment_methods_dict[pm]['total'] += t.amount
    
    payment_methods = [(pm, data['count'], data['total']) for pm, data in payment_methods_dict.items()]
    
    # Get recent transactions
    recent_transactions = q.order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('finance/transactions/dashboard.html',
                         total_transactions=total_transactions,
                         total_amount=total_amount,
                         monthly_transactions=monthly_transactions,
                         monthly_amount=monthly_amount,
                         payment_methods=payment_methods,
                         recent_transactions=recent_transactions)
