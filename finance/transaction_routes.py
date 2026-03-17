from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Transaction, Client, Invoice
from datetime import datetime, date
from functools import wraps

transaction_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

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
    clients = Client.query.all()
    
    return render_template('finance/transactions/list.html',
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
            
            transaction = Transaction(
                client_id=client_id,
                invoice_id=invoice_id if invoice_id else None,
                amount=amount,
                payment_method=payment_method,
                payment_date=payment_date,
                transaction_reference=transaction_reference,
                bank_account=bank_account,
                notes=notes,
                status='Completed'
            )
            
            db.session.add(transaction)
            
            # Update invoice paid amount if invoice is linked
            if invoice_id:
                invoice = Invoice.query.get(invoice_id)
                if invoice:
                    invoice.paid_amount += amount
                    if invoice.paid_amount >= invoice.amount:
                        invoice.status = 'Paid'
                    else:
                        invoice.status = 'Partially Paid'
                    
                    # Update client payment status
                    invoice.contract.quotation.client.payment_status = 'Partially Paid'
            
            db.session.commit()
            
            flash('Transaction recorded successfully!', 'success')
            return redirect(url_for('transactions.transaction_list'))
            
        except Exception as e:
            flash(f'Error adding transaction: {str(e)}', 'error')
            return redirect(url_for('transactions.add_transaction'))
    
    # Get clients and invoices for dropdowns
    clients = Client.query.all()
    invoices = Invoice.query.filter(Invoice.status.in_(['Unpaid', 'Partially Paid'])).all()
    
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
            
            flash('Transaction updated successfully!', 'success')
            return redirect(url_for('transactions.transaction_list'))
            
        except Exception as e:
            flash(f'Error updating transaction: {str(e)}', 'error')
            return redirect(url_for('transactions.edit_transaction', transaction_id=transaction_id))
    
    clients = Client.query.all()
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
        if transaction.invoice_id:
            invoice = Invoice.query.get(transaction.invoice_id)
            if invoice:
                invoice.paid_amount -= transaction.amount
                if invoice.paid_amount <= 0:
                    invoice.status = 'Unpaid'
                    invoice.paid_amount = 0
                else:
                    invoice.status = 'Partially Paid'
        
        db.session.delete(transaction)
        db.session.commit()
        
        flash('Transaction deleted successfully!', 'success')
        return redirect(url_for('transactions.transaction_list'))
        
    except Exception as e:
        flash(f'Error deleting transaction: {str(e)}', 'error')
        return redirect(url_for('transactions.transaction_list'))

@transaction_bp.route('/dashboard')
@login_required
@admin_required
def transaction_dashboard():
    # Get transaction statistics
    total_transactions = Transaction.query.count()
    total_amount = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0
    
    # Get current month transactions
    current_month = date.today().replace(day=1)
    monthly_transactions = Transaction.query.filter(Transaction.payment_date >= current_month).count()
    monthly_amount = db.session.query(db.func.sum(Transaction.amount)).filter(Transaction.payment_date >= current_month).scalar() or 0
    
    # Get payment method breakdown
    payment_methods = db.session.query(
        Transaction.payment_method,
        db.func.count(Transaction.transaction_id).label('count'),
        db.func.sum(Transaction.amount).label('total')
    ).group_by(Transaction.payment_method).all()
    
    # Get recent transactions
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('finance/transactions/dashboard.html',
                         total_transactions=total_transactions,
                         total_amount=total_amount,
                         monthly_transactions=monthly_transactions,
                         monthly_amount=monthly_amount,
                         payment_methods=payment_methods,
                         recent_transactions=recent_transactions)
