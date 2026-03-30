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
            
    # Re-fetch after updates class
    clients = Client.query.all()
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
