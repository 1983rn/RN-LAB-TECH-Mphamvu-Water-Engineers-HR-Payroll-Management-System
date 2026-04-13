from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from functools import wraps
from models import Client, ClientCreditScore
from db_utils import db
from utils.credit_scoring import update_client_credit_score

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')

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
        if session.get('role') not in ['Administrator', 'Director', 'HR Manager', 'Accountant']:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@clients_bp.route('/credit-scoring')
@login_required
@admin_required
def credit_scoring():
    clients = Client.query.all()
    # Ensure all clients have a score
    for client in clients:
        if not client.credit_scores:
            update_client_credit_score(client.client_id)
            
    # Re-fetch after updates class, sorting by credit score (1 is best, 6 is worst)
    clients = Client.query.outerjoin(ClientCreditScore).order_by(ClientCreditScore.score.asc(), Client.created_at.desc()).all()
    return render_template('clients/credit_scoring.html', clients=clients)

@clients_bp.route('/recalculate-score/<int:client_id>', methods=['POST'])
@login_required
@admin_required
def recalculate_score(client_id):
    score_record = update_client_credit_score(client_id)
    if score_record:
        flash('Credit score recalculated successfully.', 'success')
    else:
        flash('Failed to recalculate credit score: Client not found.', 'error')
    return redirect(url_for('clients.credit_scoring'))

@clients_bp.route('/')
@login_required
def list_clients():
    # Sort clients by their credit score (1 is best, 6 is worst) so the highest ranked are at the top
    clients = Client.query.outerjoin(ClientCreditScore).order_by(ClientCreditScore.score.asc(), Client.created_at.desc()).all()
    return render_template('clients/list.html', clients=clients)

@clients_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_client():
    if request.method == 'POST':
        try:
            client_name = request.form['client_name']
            phone = request.form['phone']
            email = request.form.get('email')
            address = request.form['address']
            project_type = request.form['project_type']
            
            # Check if client already exists by phone
            existing_client = Client.query.filter_by(phone=phone).first()
            if existing_client:
                flash(f'A client with phone number {phone} already exists.', 'error')
                return redirect(url_for('clients.add_client'))
                
            new_client = Client(
                client_name=client_name,
                phone=phone,
                email=email,
                address=address,
                project_type=project_type
            )
            db.session.add(new_client)
            db.session.commit()
            
            # Initial credit score
            update_client_credit_score(new_client.client_id)
            
            flash(f'Client {client_name} added successfully.', 'success')
            return redirect(url_for('clients.list_clients'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding client: {str(e)}', 'error')
            return redirect(url_for('clients.add_client'))
            
    return render_template('clients/add.html')

@clients_bp.route('/delete/<int:client_id>', methods=['POST'])
@login_required
@admin_required
def delete_client(client_id):
    try:
        from models import Quotation # Avoid circular import if needed, though they are usually in same models.py
        client = Client.query.get_or_404(client_id)
        
        # Check if client has quotations
        if client.quotations:
            # We might want to allow deletion anyway if confirmed, but for safety:
            flash(f'Cannot delete client {client.client_name} because they have associated quotations. Delete quotations first.', 'error')
            return redirect(url_for('clients.list_clients'))
            
        db.session.delete(client)
        db.session.commit()
        flash(f'Client {client.client_name} deleted successfully.', 'success')
        return redirect(url_for('clients.list_clients'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting client: {str(e)}', 'error')
        return redirect(url_for('clients.list_clients'))
