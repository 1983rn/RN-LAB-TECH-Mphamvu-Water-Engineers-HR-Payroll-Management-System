from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from functools import wraps
from models import Client, ClientCreditScore, CustomProjectType
from db_utils import db
from utils.credit_scoring import update_client_credit_score
from utils.auth_utils import apply_dept_filter, get_current_dept

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


@clients_bp.route('/recalculate-all', methods=['POST'])
@login_required
@admin_required
def recalculate_all_scores():
    query = Client.query
    clients = apply_dept_filter(query, Client).all()
    for client in clients:
        update_client_credit_score(client.client_id)
    flash('All credit scores have been uniformly recalculated.', 'success')
    return redirect(url_for('clients.list_clients'))

@clients_bp.route('/')
@login_required
def list_clients():
    query = Client.query
    query = apply_dept_filter(query, Client)
    
    # Sort clients by their credit score highest first
    clients = query.order_by(Client.credit_score.desc(), Client.created_at.desc()).all()
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
                project_type=project_type,
                department=get_current_dept()
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
            
    custom_types = CustomProjectType.query.filter_by(department=get_current_dept()).all()
    return render_template('clients/add.html', custom_types=custom_types)

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

@clients_bp.route('/add_custom_project_type', methods=['POST'])
@login_required
def add_custom_project_type():
    data = request.get_json()
    project_type_name = data.get('project_type', '').strip()
    
    if not project_type_name:
        return jsonify({'success': False, 'message': 'Project type name is required'}), 400
        
    try:
        # Check if already exists globally due to unique constraint
        dept = get_current_dept()
        existing = CustomProjectType.query.filter_by(project_type=project_type_name).first()
        if existing:
            # If it already exists, just return success so the user can use it
            return jsonify({'success': True, 'message': 'Project type added successfully'})
            
        new_type = CustomProjectType(
            project_type=project_type_name,
            department=dept
        )
        db.session.add(new_type)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Project type added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
