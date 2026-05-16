from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from functools import wraps
from models import db, Client, Quotation, Invoice, Transaction, SupportRequest, ICTProject, ICTDeveloper, ICTTask, ICTTraining, Employee, Inventory, CashBookEntry, DeliveryNote, QuotationItem, Contract
from datetime import datetime
from utils.pdf_utils import generate_receipt_pdf
from utils.quotation_location import parse_optional_coord
import io

ict_bp = Blueprint('ict', __name__, url_prefix='/ict')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def ict_context_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('department_context') != 'ICT Department':
            session['department_context'] = 'ICT Department'
            session['department_dashboard'] = 'ict.dashboard'
        return f(*args, **kwargs)
    return decorated_function

@ict_bp.route('/dashboard')
@login_required
@ict_context_required
def dashboard():
    stats = {
        'active_projects': ICTProject.query.filter(ICTProject.status != 'Completed').count(),
        'total_clients': Client.query.filter_by(department='ICT').count(),
        'pending_tasks': ICTTask.query.filter(ICTTask.status != 'Completed').count(),
        'upcoming_trainings': ICTTraining.query.filter(ICTTraining.status == 'Scheduled').count()
    }
    
    projects = ICTProject.query.order_by(ICTProject.created_at.desc()).limit(5).all()
    tasks = ICTTask.query.filter(ICTTask.status != 'Completed').order_by(ICTTask.due_date).limit(5).all()
    
    return render_template('ict/dashboard.html', stats=stats, projects=projects, tasks=tasks)

@ict_bp.route('/exit')
@login_required
def exit_department():
    session.pop('department_context', None)
    session.pop('department_dashboard', None)
    return redirect(url_for('dashboard'))

@ict_bp.route('/projects')
@login_required
@ict_context_required
def projects():
    all_projects = ICTProject.query.order_by(ICTProject.created_at.desc()).all()
    return render_template('ict/projects.html', projects=all_projects)

@ict_bp.route('/projects/create', methods=['POST'])
@login_required
@ict_context_required
def create_project():
    try:
        new_project = ICTProject(
            project_name=request.form['project_name'],
            project_type=request.form['project_type'],
            description=request.form['description'],
            status='Pending'
        )
        if request.form.get('client_id'):
            new_project.client_id = int(request.form['client_id'])
            
        if request.form.get('start_date'):
            new_project.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
            
        if request.form.get('end_date'):
            new_project.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
            
        db.session.add(new_project)
        db.session.commit()
        flash('ICT Project created successfully', 'success')
    except Exception as e:
        flash(f'Error creating project: {str(e)}', 'error')
        db.session.rollback()
        
    return redirect(url_for('ict.projects'))

@ict_bp.route('/tasks')
@login_required
@ict_context_required
def tasks():
    all_tasks = ICTTask.query.order_by(ICTTask.due_date).all()
    projects = ICTProject.query.all()
    developers = ICTDeveloper.query.all()
    return render_template('ict/tasks.html', tasks=all_tasks, projects=projects, developers=developers)

@ict_bp.route('/tasks/create', methods=['POST'])
@login_required
@ict_context_required
def create_task():
    try:
        new_task = ICTTask(
            project_id=request.form['project_id'],
            task_name=request.form['task_name'],
            description=request.form['description'],
            status='Pending'
        )
        if request.form.get('developer_id'):
            new_task.developer_id = request.form['developer_id']
            
        if request.form.get('due_date'):
            new_task.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date()
            
        db.session.add(new_task)
        db.session.commit()
        flash('Task assigned successfully', 'success')
    except Exception as e:
        flash(f'Error creating task: {str(e)}', 'error')
        db.session.rollback()
        
    return redirect(url_for('ict.tasks'))

@ict_bp.route('/developers')
@login_required
@ict_context_required
def developers():
    all_devs = ICTDeveloper.query.all()
    employees = Employee.query.filter_by(status='Active').all() # All active employees can potentially be added as developers
    return render_template('ict/developers.html', developers=all_devs, employees=employees)

@ict_bp.route('/developers/add', methods=['POST'])
@login_required
@ict_context_required
def add_developer():
    try:
        new_dev = ICTDeveloper(
            employee_id=request.form['employee_id'],
            skills=request.form['skills'],
            availability=request.form['availability']
        )
        db.session.add(new_dev)
        db.session.commit()
        flash('Developer added successfully', 'success')
    except Exception as e:
        flash(f'Error adding developer: {str(e)}', 'error')
        db.session.rollback()
        
    return redirect(url_for('ict.developers'))

@ict_bp.route('/trainings')
@login_required
@ict_context_required
def trainings():
    all_trainings = ICTTraining.query.order_by(ICTTraining.schedule_date.desc()).all()
    clients = Client.query.filter_by(department='ICT').all()
    employees = Employee.query.filter_by(status='Active').all()
    return render_template('ict/trainings.html', trainings=all_trainings, clients=clients, employees=employees)

@ict_bp.route('/trainings/schedule', methods=['POST'])
@login_required
@ict_context_required
def schedule_training():
    try:
        new_training = ICTTraining(
            training_name=request.form['training_name'],
            schedule_date=datetime.strptime(request.form['schedule_date'], '%Y-%m-%dT%H:%M'),
            status='Scheduled'
        )
        if request.form.get('client_id'):
            new_training.client_id = request.form['client_id']
        if request.form.get('trainer_id'):
            new_training.trainer_id = request.form['trainer_id']
        if request.form.get('training_fee'):
            new_training.training_fee = float(request.form['training_fee'])
            
        db.session.add(new_training)
        db.session.commit()
        flash('Training scheduled successfully', 'success')
    except Exception as e:
        flash(f'Error scheduling training: {str(e)}', 'error')
        db.session.rollback()
        
    return redirect(url_for('ict.trainings'))

@ict_bp.route('/clients')
@login_required
@ict_context_required
def clients():
    all_clients = Client.query.filter_by(department='ICT').all()
    return render_template('ict/clients.html', clients=all_clients)

# ==========================================
# FINANCIAL & INVENTORY MODULES
# ==========================================

@ict_bp.route('/quotations')
@login_required
@ict_context_required
def quotations():
    quos = Quotation.query.filter_by(department='ICT Department').order_by(Quotation.created_at.desc()).all()
    clients = Client.query.filter_by(department='ICT Department').all()
    return render_template('ict/quotations.html', quotations=quos, clients=clients)

@ict_bp.route('/quotations/create', methods=['POST'])
@login_required
@ict_context_required
def create_quotation():
    client_id = request.form.get('client_id')
    location = request.form.get('location')
    amount = float(request.form.get('total_amount', 0))
    
    new_quo = Quotation(
        client_id=client_id,
        project_location=location,
        project_latitude=parse_optional_coord(request.form, 'project_latitude'),
        project_longitude=parse_optional_coord(request.form, 'project_longitude'),
        total_amount=amount,
        department='ICT Department',
        status='Pending'
    )
    db.session.add(new_quo)
    db.session.commit()
    flash('ICT Quotation created successfully!', 'success')
    return redirect(url_for('ict.quotations'))

@ict_bp.route('/invoices')
@login_required
@ict_context_required
def invoices():
    invs = Invoice.query.filter_by(department='ICT Department').order_by(Invoice.created_at.desc()).all()
    quos = Quotation.query.filter_by(department='ICT Department', status='Approved').all()
    return render_template('ict/invoices.html', invoices=invs, quotations=quos)

@ict_bp.route('/invoices/create', methods=['POST'])
@login_required
@ict_context_required
def create_invoice():
    quo_id = request.form.get('quotation_id')
    quo = Quotation.query.get_or_404(quo_id)
    
    # Check if invoice already exists
    if quo.invoice_generated:
        flash('Invoice already generated for this quotation.', 'warning')
        return redirect(url_for('ict.invoices'))
    
    # ICT usually needs a contract first
    contract = Contract.query.filter_by(quotation_id=quo_id).first()
    if not contract:
        contract = Contract(quotation_id=quo_id, contract_date=datetime.utcnow().date(), department='ICT Department')
        db.session.add(contract)
        db.session.flush()

    new_inv = Invoice(
        quotation_id=quo_id,
        contract_id=contract.contract_id,
        invoice_number=f"INV-ICT-{datetime.now().strftime('%y%m%d%H%M')}",
        invoice_date=datetime.utcnow().date(),
        due_date=datetime.utcnow().date(), 
        amount=quo.total_amount,
        department='ICT Department'
    )
    quo.invoice_generated = True
    db.session.add(new_inv)
    db.session.commit()
    flash('ICT Invoice generated successfully!', 'success')
    return redirect(url_for('ict.invoices'))

@ict_bp.route('/delivery_notes')
@login_required
@ict_context_required
def delivery_notes():
    dns = DeliveryNote.query.filter_by(department='ICT Department').order_by(DeliveryNote.created_at.desc()).all()
    invs = Invoice.query.filter_by(department='ICT Department').all()
    return render_template('ict/delivery_notes.html', delivery_notes=dns, invoices=invs)

@ict_bp.route('/delivery_notes/create', methods=['POST'])
@login_required
@ict_context_required
def create_delivery_note():
    inv_id = request.form.get('invoice_id')
    inv = Invoice.query.get_or_404(inv_id)
    
    new_dn = DeliveryNote(
        invoice_id=inv_id,
        quotation_id=inv.quotation_id,
        delivery_date=datetime.utcnow().date(),
        equipment_delivered=request.form.get('equipment', 'ICT Services/Software'),
        delivered_by=session.get('username', 'ICT System'),
        department='ICT Department'
    )
    db.session.add(new_dn)
    db.session.commit()
    flash('ICT Delivery Note created successfully!', 'success')
    return redirect(url_for('ict.delivery_notes'))

@ict_bp.route('/generate_receipt/<int:delivery_id>', methods=['POST'])
@login_required
@ict_context_required
def generate_receipt(delivery_id):
    dn = DeliveryNote.query.get_or_404(delivery_id)
    inv = dn.invoice
    
    # Create transaction if it doesn't exist
    tx = Transaction.query.filter_by(invoice_id=inv.invoice_id).first()
    if not tx:
        tx = Transaction(
            client_id=inv.quotation.client_id,
            invoice_id=inv.invoice_id,
            amount=inv.amount,
            payment_method='Bank Transfer',
            payment_date=datetime.utcnow().date(),
            status='Completed',
            notes=f'Payment for ICT {inv.invoice_number}',
            department='ICT Department'
        )
        inv.paid_amount = inv.amount
        inv.status = 'Paid'
        db.session.add(tx)
        
        # Add to Cashbook
        entry = CashBookEntry(
            date=datetime.utcnow().date(),
            description=f"Income: ICT Project {inv.invoice_number}",
            reference=inv.invoice_number,
            amount=inv.amount,
            type='Credit',
            category='ICT Revenue',
            department='ICT Department'
        )
        db.session.add(entry)
        db.session.commit()

    # Generate PDF
    pdf_buffer = generate_receipt_pdf(tx, department='ICT Department')
    return send_file(
        io.BytesIO(pdf_buffer),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ICT_Receipt_{inv.invoice_number}.pdf"
    )

@ict_bp.route('/cashbook')
@login_required
@ict_context_required
def cashbook():
    entries = CashBookEntry.query.filter_by(department='ICT Department').order_by(CashBookEntry.date.desc()).all()
    total_income = sum(e.amount for e in entries if e.type == 'Credit')
    total_expense = sum(e.amount for e in entries if e.type == 'Debit')
    return render_template('ict/cashbook.html', entries=entries, total_income=total_income, total_expense=total_expense)

@ict_bp.route('/inventory')
@login_required
@ict_context_required
def inventory():
    items = Inventory.query.filter_by(department='ICT Department').all()
    total_value = sum((item.total_value or 0.0) for item in items)
    return render_template('ict/inventory.html', items=items, total_value=total_value)

@ict_bp.route('/inventory/add', methods=['POST'])
@login_required
@ict_context_required
def add_inventory():
    name = request.form.get('asset_name')
    category = request.form.get('category')
    qty = int(request.form.get('quantity', 0))
    unit_val = float(request.form.get('unit_value', 0))
    
    new_item = Inventory(
        asset_name=name,
        category=category,
        quantity=qty,
        unit_value=unit_val,
        total_value=qty * unit_val,
        department='ICT Department',
        condition=request.form.get('condition', 'New'),
        description=request.form.get('description')
    )
    db.session.add(new_item)
    db.session.commit()
    flash('ICT Inventory item added!', 'success')
    return redirect(url_for('ict.inventory'))
