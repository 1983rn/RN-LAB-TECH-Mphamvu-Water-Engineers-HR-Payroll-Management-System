from flask import Blueprint, render_template, request, flash, redirect, url_for, session, send_file
from functools import wraps
from models import (ConstructionProject, ConstructionCost, ConstructionStock, 
                    Quotation, Invoice, DeliveryNote, Transaction, CashBookEntry, Client, Inventory)
from db_utils import db
from datetime import datetime
import sqlalchemy as sa
from utils.pdf_utils import generate_receipt_pdf
from utils.auth_utils import apply_dept_filter, get_current_dept

construction_bp = Blueprint('construction', __name__, url_prefix='/construction')

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
            return redirect(url_for('construction.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@construction_bp.route('/', methods=['GET'])
@login_required
@admin_required
def dashboard():
    # Context for UI
    session['department_context'] = 'Construction'
    session['department_dashboard'] = 'construction.dashboard'

    # --- Materials Data ---
    materials = ConstructionStock.query.all()
    cement_stock = ConstructionStock.query.filter(ConstructionStock.item_name.ilike('%cement%')).first()
    bricks_stock = ConstructionStock.query.filter(ConstructionStock.item_name.ilike('%brick%')).first()

    # --- Project Data ---
    proj_query = apply_dept_filter(ConstructionProject.query, ConstructionProject)
    projects = proj_query.order_by(ConstructionProject.created_at.desc()).all()
    active_projects = [p for p in projects if p.status == 'In Progress']
    
    # --- Financial Data (Filtered by Construction Department) ---
    quotes = apply_dept_filter(Quotation.query, Quotation).order_by(Quotation.created_at.desc()).all()
    invoices = apply_dept_filter(Invoice.query, Invoice).order_by(Invoice.created_at.desc()).all()
    
    del_query = DeliveryNote.query.join(Quotation)
    # Apply dept filter using DeliveryNote model (it has department now)
    deliveries = apply_dept_filter(DeliveryNote.query, DeliveryNote).order_by(DeliveryNote.created_at.desc()).all()
    
    transactions = apply_dept_filter(Transaction.query, Transaction).order_by(Transaction.payment_date.desc()).all()
    cashbook = apply_dept_filter(CashBookEntry.query, CashBookEntry).order_by(CashBookEntry.date.desc()).all()
    
    # --- Client & Asset Data ---
    clients = apply_dept_filter(Client.query, Client).all()
    inventory = apply_dept_filter(Inventory.query, Inventory).all()

    # --- Summary Stats ---
    total_revenue = sum(t.amount for t in transactions)
    total_project_cost = sum(p.actual_cost for p in projects)
    
    return render_template('construction/dashboard.html',
                          materials=materials,
                          cement=cement_stock,
                          bricks=bricks_stock,
                          projects=projects,
                          active_projects_count=len(active_projects),
                          quotes=quotes,
                          invoices=invoices,
                          deliveries=deliveries,
                          transactions=transactions,
                          cashbook=cashbook,
                          clients=clients,
                          inventory=inventory,
                          total_revenue=total_revenue,
                          total_project_cost=total_project_cost,
                          now=datetime.now())

# --- Materials Stock Management ---

@construction_bp.route('/materials/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_material():
    if request.method == 'POST':
        name = request.form.get('item_name')
        qty = float(request.form.get('quantity', 0))
        unit = request.form.get('unit')
        price = float(request.form.get('unit_price', 0))
        
        stock = ConstructionStock.query.filter_by(item_name=name).first()
        if stock:
            stock.quantity += qty
            stock.unit_price = price
            stock.total_value = stock.quantity * price
            stock.last_restock_date = datetime.now()
        else:
            stock = ConstructionStock(
                item_name=name,
                quantity=qty,
                unit=unit,
                unit_price=price,
                total_value=qty * price,
                last_restock_date=datetime.now()
            )
            db.session.add(stock)
        
        # Log to Cashbook (Debit - Buying Materials)
        entry = CashBookEntry(
            description=f"Initial Stock/Restock: {qty} {unit} of {name}",
            amount=qty * price,
            type='Debit',
            category='Material Purchase',
            department='Construction',
            date=datetime.now().date()
        )
        db.session.add(entry)
        
        db.session.commit()
        flash(f'Restocked {name} successfully.', 'success')
        return redirect(url_for('construction.dashboard'))
    
    from models import CustomProjectType
    custom_types = CustomProjectType.query.filter_by(department='Construction').all()
    return render_template('construction/material_form.html', now=datetime.now(), custom_types=[t.project_type for t in custom_types])

# --- Project Management ---

@construction_bp.route('/projects/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_project():
    if request.method == 'POST':
        project = ConstructionProject(
            project_name=request.form.get('project_name'),
            client_id=request.form.get('client_id'),
            location=request.form.get('location'),
            description=request.form.get('description'),
            estimated_budget=float(request.form.get('budget', 0)),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None,
            status='In Progress',
            department=get_current_dept()
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully.', 'success')
        return redirect(url_for('construction.dashboard'))
    
    clients = apply_dept_filter(Client.query, Client).all()
    return render_template('construction/project_form.html', clients=clients, now=datetime.now())

@construction_bp.route('/projects/cost/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_cost():
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        cost_type = request.form.get('cost_type')
        desc = request.form.get('description')
        amt = float(request.form.get('amount', 0))
        
        cost = ConstructionCost(
            project_id=project_id,
            cost_type=cost_type,
            description=desc,
            amount=amt,
            date=datetime.now().date(),
            department=get_current_dept()
        )
        db.session.add(cost)
        
        # Update Project Actual Cost
        project = ConstructionProject.query.get(project_id)
        project.update_actual_cost()
        
        # Log to Cashbook (Debit - Project Expense)
        entry = CashBookEntry(
            description=f"Proj Expense: {project.project_name} - {cost_type} ({desc})",
            amount=amt,
            type='Debit',
            category='Project cost',
            department='Construction',
            date=datetime.now().date()
        )
        db.session.add(entry)
        
        db.session.commit()
        flash('Cost record added and project updated.', 'success')
        return redirect(url_for('construction.dashboard'))
    
    projects = ConstructionProject.query.all()
    return render_template('construction/cost_form.html', projects=projects, now=datetime.now())

# --- Receipt Generation from Delivery Note ---

@construction_bp.route('/receipt/<int:delivery_id>', methods=['POST'])
@login_required
@admin_required
def generate_receipt_from_delivery(delivery_id):
    delivery = DeliveryNote.query.get_or_404(delivery_id)
    # 1. Create a transaction for this delivery if it was paid
    amount = float(request.form.get('amount', 0))
    method = request.form.get('payment_method', 'Cash')
    
    tx = Transaction(
        client_id=delivery.quotation.client_id,
        amount=amount,
        payment_method=method,
        payment_date=datetime.now().date(),
        notes=f"Payment for Delivery {delivery.reference_number}",
        department=delivery.department
    )
    db.session.add(tx)
    
    # Log to Cashbook (Credit - Income)
    entry = CashBookEntry(
        description=f"Construction Income: {delivery.quotation.client.client_name} (Del: {delivery.reference_number})",
        amount=amount,
        type='Credit',
        category='Sales',
        department='Construction',
        date=datetime.now().date()
    )
    db.session.add(entry)
    
    db.session.commit()
    
    # 2. Generate and return the PDF receipt
    try:
        pdf_buffer = generate_receipt_pdf(tx)
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"Receipt_{tx.reference_number}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error generating receipt: {str(e)}', 'error')
        return redirect(url_for('construction.dashboard'))

@construction_bp.route('/materials/use', methods=['GET', 'POST'])
@login_required
@admin_required
def use_material():
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        stock_id = request.form.get('stock_id')
        qty_to_use = float(request.form.get('quantity', 0))
        
        stock = ConstructionStock.query.get_or_404(stock_id)
        project = ConstructionProject.query.get_or_404(project_id)
        
        if stock.quantity < qty_to_use:
            flash(f'Insufficient stock for {stock.item_name}. Available: {stock.quantity}', 'error')
            return redirect(url_for('construction.dashboard'))
            
        # 1. Deduct Stock
        stock.quantity -= qty_to_use
        stock.total_value = stock.quantity * stock.unit_price
        
        # 2. Create Project Cost Entry
        val_used = qty_to_use * stock.unit_price
        cost = ConstructionCost(
            project_id=project.id,
            cost_type='Raw materials',
            description=f"Material Use: {qty_to_use} {stock.unit} of {stock.item_name}",
            amount=val_used,
            date=datetime.now().date()
        )
        db.session.add(cost)
        
        # 3. Update Project Total
        project.update_actual_cost()
        
        db.session.commit()
        flash(f'Issued {qty_to_use} {stock.unit} of {stock.item_name} to project: {project.project_name}', 'success')
        return redirect(url_for('construction.dashboard'))
    
    projects = ConstructionProject.query.all()
    materials = ConstructionStock.query.all()
    return render_template('construction/use_material_form.html', projects=projects, materials=materials, now=datetime.now())
