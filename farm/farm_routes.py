from flask import Blueprint, render_template, request, flash, redirect, url_for, session, send_file, jsonify
from functools import wraps
from models import FarmActivity, FarmInput, FarmOutput, FarmExpense, Livestock, CropCycle, Transaction, CashBookEntry, Quotation, Invoice, DeliveryNote, Inventory, CustomInventoryCategory
from utils.auth_utils import apply_dept_filter, get_current_dept
from db_utils import db
from datetime import datetime, date
import sqlalchemy as sa
from utils.pdf_utils import generate_receipt_pdf

farm_bp = Blueprint('farm', __name__, url_prefix='/farm')

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

@farm_bp.route('/', methods=['GET'])
@login_required
@admin_required
def dashboard():
    # Set context for sidebar/navigation
    session['department_context'] = 'Farm'
    session['department_dashboard'] = 'farm.dashboard'

    # --- Livestock Data ---
    animals_query = apply_dept_filter(Livestock.query, Livestock)
    animals = animals_query.order_by(Livestock.created_at.desc()).all()
    livestock_count = len([a for a in animals if a.status == 'Alive'])
    losses_count = len([a for a in animals if a.status == 'Dead'])
    
    # Simple logic for monthly births
    first_of_month = date.today().replace(day=1)
    monthly_births = animals_query.filter(Livestock.birth_date >= first_of_month).count()

    # --- Crops Data ---
    crops_query = apply_dept_filter(CropCycle.query, CropCycle)
    active_crops_list = crops_query.filter_by(status='Growing').all()
    active_crops_count = len(active_crops_list)
    last_harvest = crops_query.filter_by(status='Harvested').order_by(CropCycle.actual_harvest_date.desc()).first()
    last_harvest_qty = last_harvest.quantity_harvested if last_harvest else 0

    # --- Inputs Data ---
    inputs_query = apply_dept_filter(FarmInput.query, FarmInput)
    farm_inputs = inputs_query.order_by(FarmInput.date_added.desc()).all()

    # --- Farm Inventory Data ---
    inventory_query = apply_dept_filter(Inventory.query, Inventory)
    farm_inventory = inventory_query.all()

    # --- Finance Data ---
    # We query transactions and cashbook entries specifically for the Farm department
    txs_query = apply_dept_filter(Transaction.query, Transaction)
    txs = txs_query.all()
    
    cash_query = apply_dept_filter(CashBookEntry.query, CashBookEntry)
    cash_entries = cash_query.all()
    
    # Combined Cashbook Entries for the Dashboard
    finance_entries = []
    for t in txs:
        finance_entries.append({
            'date': t.payment_date,
            'description': t.notes or f"Farm Sale - {t.client.client_name if t.client else 'Cash'}",
            'ref': t.reference_number or 'SALE',
            'category': 'Business Revenue',
            'type': 'Credit',
            'amount': float(t.amount or 0.0)
        })
    for e in cash_entries:
        finance_entries.append({
            'date': e.date,
            'description': e.description,
            'ref': e.reference or 'FARM',
            'category': e.category or 'Operations',
            'type': e.type,
            'amount': float(e.amount or 0.0)
        })
    finance_entries.sort(key=lambda x: x['date'], reverse=True)

    sales_total = sum((t.amount or 0.0) for t in txs)
    total_income = sales_total + sum((e.amount or 0.0) for e in cash_entries if e.type == 'Credit' and "Opening Balance" not in e.description)
    total_expense = sum((e.amount or 0.0) for e in cash_entries if e.type == 'Debit')
    
    # Opening balance for Farm
    ob_entry = CashBookEntry.query.filter(
        CashBookEntry.department == 'Farm',
        CashBookEntry.description.ilike('%Opening Balance%')
    ).first()
    opening_balance = float(ob_entry.amount) if ob_entry else 0.0
    
    net_profit = (opening_balance + total_income) - total_expense

    # --- Sales Workflow Data ---
    quotes_query = apply_dept_filter(Quotation.query, Quotation)
    farm_quotes = quotes_query.order_by(Quotation.created_at.desc()).all()

    inv_query = apply_dept_filter(Invoice.query, Invoice)
    farm_invoices = inv_query.order_by(Invoice.created_at.desc()).all()

    del_query = apply_dept_filter(DeliveryNote.query, DeliveryNote)
    farm_deliveries = del_query.order_by(DeliveryNote.created_at.desc()).all()
    
    return render_template('farm/dashboard.html', 
                          animals=animals,
                          livestock_count=livestock_count,
                          monthly_births=monthly_births,
                          losses_count=losses_count,
                          sales_total=sales_total,
                          active_crops=active_crops_count,
                          active_crops_list=active_crops_list,
                          last_harvest_qty=last_harvest_qty,
                          farm_inputs=farm_inputs,
                          total_income=total_income,
                          total_expense=total_expense,
                          net_profit=net_profit,
                          txs=txs,
                          finance_entries=finance_entries[:20], # Show last 20 for dashboard
                          quotes=farm_quotes,
                          invoices=farm_invoices,
                          deliveries=farm_deliveries,
                          farm_inventory=farm_inventory,
                          now=datetime.now())

@farm_bp.route('/cashbook')
@login_required
@admin_required
def cashbook():
    # 1. Get Manual CashBook Entries
    entries_query = apply_dept_filter(CashBookEntry.query, CashBookEntry)
    entries = entries_query.order_by(CashBookEntry.date.desc()).all()
    
    # 2. Get Business Transactions (Client Payments/Sales)
    tx_query = apply_dept_filter(Transaction.query, Transaction)
    transactions = tx_query.all()
    
    credits_list = []
    debits_list = []
    
    for t in transactions:
        credits_list.append({
            'date': t.payment_date,
            'description': t.notes or f"Farm Sale - {t.client.client_name if t.client else 'Cash'}",
            'ref': t.reference_number,
            'amount': float(t.amount) if t.amount else 0.0,
            'category': 'Business Revenue',
            'department': 'Farm'
        })
        
    for e in entries:
        item = {
            'date': e.date,
            'description': e.description,
            'ref': e.reference or 'FARM',
            'amount': float(e.amount) if e.amount else 0.0,
            'category': e.category or 'Operations',
            'department': e.department
        }
        if e.type == 'Credit':
            credits_list.append(item)
        else:
            debits_list.append(item)
            
    ob_entry = entries_query.filter(CashBookEntry.description.ilike('%Opening Balance%')).first()
    opening_balance = float(ob_entry.amount) if ob_entry else 0.0
    
    # Total Input Asset Value
    input_query = apply_dept_filter(FarmInput.query, FarmInput)
    total_inventory = input_query.with_entities(sa.func.sum(FarmInput.total_cost)).scalar() or 0.0
    
    total_income = sum((c['amount'] or 0.0) for c in credits_list if "Opening Balance" not in c['description'])
    total_debits = sum((d['amount'] or 0.0) for d in debits_list)
    balance = opening_balance + total_income - total_debits
    
    income_breakdown = {}
    for c in credits_list:
        if "Opening Balance" in c['description']: continue
        cat = c['category']
        income_breakdown[cat] = income_breakdown.get(cat, 0) + c['amount']
        
    expense_breakdown = {}
    for d in debits_list:
        cat = d['category']
        expense_breakdown[cat] = expense_breakdown.get(cat, 0) + d['amount']
    
    credits_list.sort(key=lambda x: x['date'], reverse=True)
    debits_list.sort(key=lambda x: x['date'], reverse=True)

    return render_template('farm/cashbook.html', 
                           credits=credits_list,
                           debits=debits_list,
                           total_income=total_income,
                           total_debits=total_debits,
                           opening_balance=opening_balance,
                           balance=balance,
                           total_inventory=total_inventory,
                           income_breakdown=income_breakdown,
                           expense_breakdown=expense_breakdown,
                           now=datetime.now(),
                           is_farm=True)

@farm_bp.route('/cashbook/add', methods=['POST'])
@login_required
@admin_required
def add_cashbook_entry():
    try:
        date_str = request.form.get('date')
        description = request.form.get('description')
        amount_str = request.form.get('amount')
        entry_type = request.form.get('type')

        if not all([date_str, description, amount_str, entry_type]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('farm.cashbook'))

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        amount = float(amount_str)
        reference = request.form.get('reference')
        category = request.form.get('category')

        entry = CashBookEntry(
            date=date_obj,
            description=description,
            reference=reference,
            amount=amount,
            type=entry_type,
            category=category,
            department='Farm'
        )
        db.session.add(entry)
        db.session.commit()
        flash('Entry added to Farm Cash Book successfully!', 'success')
    except ValueError:
        flash('Error: Invalid date or amount format.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding entry: {str(e)}', 'error')

    return redirect(url_for('farm.cashbook'))

# --- Livestock Routes ---
@farm_bp.route('/livestock/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_livestock():
    if request.method == 'POST':
        try:
            new_animal = Livestock(
                animal_type=request.form.get('animal_type'),
                tag_number=request.form.get('tag_number'),
                gender=request.form.get('gender'),
                breed=request.form.get('breed'),
                birth_date=datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date() if request.form.get('birth_date') else None,
                purchase_price=float(request.form.get('purchase_price', 0)),
                notes=request.form.get('notes'),
                department=get_current_dept()
            )
            db.session.add(new_animal)
            db.session.commit()
            flash('Livestock record added successfully.', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding livestock: {str(e)}', 'error')
            
    return render_template('farm/livestock_form.html', animal=None)

@farm_bp.route('/livestock/status/<int:animal_id>', methods=['POST'])
@login_required
@admin_required
def update_livestock_status(animal_id):
    animal = Livestock.query.get_or_404(animal_id)
    new_status = request.form.get('status')
    
    if new_status == 'Dead':
        animal.death_date = date.today()
    
    animal.status = new_status
    db.session.commit()
    flash(f'Status updated to {new_status}.', 'success')
    return redirect(url_for('farm.dashboard'))

@farm_bp.route('/activity/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_activity():
    if request.method == 'POST':
        try:
            name = request.form.get('activity_name')
            description = request.form.get('description')
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            status = request.form.get('status', 'Planned')
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
            
            new_activity = FarmActivity(
                activity_name=name,
                description=description,
                start_date=start_date,
                end_date=end_date,
                status=status,
                department=get_current_dept()
            )
            
            db.session.add(new_activity)
            db.session.commit()
            
            flash('Farm activity created successfully.', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating activity: {str(e)}', 'error')
            
    return render_template('farm/activity_form.html', activity=None)

@farm_bp.route('/activity/<int:activity_id>', methods=['GET'])
@login_required
@admin_required
def view_activity(activity_id):
    activity = FarmActivity.query.get_or_404(activity_id)
    return render_template('farm/activity_view.html', activity=activity)

@farm_bp.route('/activity/edit/<int:activity_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_activity(activity_id):
    activity = FarmActivity.query.get_or_404(activity_id)
    
    if request.method == 'POST':
        try:
            activity.activity_name = request.form.get('activity_name')
            activity.description = request.form.get('description')
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            activity.status = request.form.get('status', 'Planned')
            
            if start_date_str:
                activity.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if end_date_str:
                activity.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                
            activity.update_profit()
            
            db.session.commit()
            flash('Farm activity updated successfully.', 'success')
            return redirect(url_for('farm.view_activity', activity_id=activity.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating activity: {str(e)}', 'error')
            
    return render_template('farm/activity_form.html', activity=activity)

@farm_bp.route('/activity/delete/<int:activity_id>', methods=['POST'])
@login_required
@admin_required
def delete_activity(activity_id):
    activity = FarmActivity.query.get_or_404(activity_id)
    try:
        db.session.delete(activity)
        db.session.commit()
        flash('Farm activity deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting activity: {str(e)}', 'error')
        
    return redirect(url_for('farm.dashboard'))

# --- Crop Routes ---
@farm_bp.route('/crops/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_crop():
    if request.method == 'POST':
        try:
            new_crop = CropCycle(
                crop_name=request.form.get('crop_name'),
                variety=request.form.get('variety'),
                planting_date=datetime.strptime(request.form.get('planting_date'), '%Y-%m-%d').date() if request.form.get('planting_date') else None,
                expected_harvest_date=datetime.strptime(request.form.get('expected_harvest_date'), '%Y-%m-%d').date() if request.form.get('expected_harvest_date') else None,
                notes=request.form.get('notes'),
                department=get_current_dept()
            )
            db.session.add(new_crop)
            db.session.commit()
            flash('Crop planting record added successfully.', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding crop: {str(e)}', 'error')
            
    return render_template('farm/crop_form.html', crop=None, now=datetime.now())

@farm_bp.route('/crops/harvest/<int:crop_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def record_harvest(crop_id):
    crop = CropCycle.query.get_or_404(crop_id)
    if request.method == 'POST':
        try:
            crop.actual_harvest_date = datetime.strptime(request.form.get('actual_harvest_date'), '%Y-%m-%d').date()
            crop.quantity_harvested = float(request.form.get('quantity_harvested', 0))
            crop.unit = request.form.get('unit', 'Bags')
            crop.status = 'Harvested'
            db.session.commit()
            flash('Harvest record updated.', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording harvest: {str(e)}', 'error')
            
    return render_template('farm/harvest_form.html', crop=crop, now=datetime.now())

# --- Expense Routes ---
@farm_bp.route('/activity/<int:activity_id>/expense/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_expense(activity_id):
    activity = FarmActivity.query.get_or_404(activity_id)
    
    if request.method == 'POST':
        try:
            category = request.form.get('category')
            description = request.form.get('description')
            amount = float(request.form.get('amount', 0))
            date_str = request.form.get('expense_date')
            
            expense_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
            
            new_expense = FarmExpense(
                activity_id=activity.id,
                expense_category=category,
                description=description,
                amount=amount,
                expense_date=expense_date,
                department=get_current_dept()
            )
            
            db.session.add(new_expense)
            activity.update_profit()
            db.session.commit()
            
            flash('Expense added successfully.', 'success')
            return redirect(url_for('farm.view_activity', activity_id=activity.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding expense: {str(e)}', 'error')
            
    return render_template('farm/expense_form.html', activity=activity)

# --- Output/Income Routes ---
@farm_bp.route('/activity/<int:activity_id>/output/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_output(activity_id):
    activity = FarmActivity.query.get_or_404(activity_id)
    
    if request.method == 'POST':
        try:
            product_name = request.form.get('product_name')
            quantity = float(request.form.get('quantity', 0))
            unit = request.form.get('unit')
            unit_price = float(request.form.get('unit_price', 0))
            
            total_value = quantity * unit_price
            
            new_output = FarmOutput(
                activity_id=activity.id,
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                total_value=total_value
            )
            
            db.session.add(new_output)
            activity.update_profit()
            db.session.commit()
            
            flash('Output/Income added successfully.', 'success')
            return redirect(url_for('farm.view_activity', activity_id=activity.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding output: {str(e)}', 'error')
            
    return render_template('farm/output_form.html', activity=activity)

# --- Input Routes ---
@farm_bp.route('/inputs/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_farm_input_stock():
    if request.method == 'POST':
        try:
            item_name = request.form.get('item_name')
            category = request.form.get('category')
            quantity = float(request.form.get('quantity', 0))
            unit = request.form.get('unit')
            unit_price = float(request.form.get('unit_price', 0))
            total_cost = quantity * unit_price
            
            new_input = FarmInput(
                item_name=item_name,
                category=category,
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                total_cost=total_cost,
                date_added=datetime.utcnow(),
                department='Farm'
            )
            
            db.session.add(new_input)
            
            # Record in Cashbook as a Debit
            new_entry = CashBookEntry(
                date=date.today(),
                description=f"Purchase of {item_name} ({category})",
                amount=total_cost,
                type='Debit',
                category='Farm Inputs',
                department='Farm'
            )
            db.session.add(new_entry)
            
            db.session.commit()
            flash('Input stock added and recorded in cashbook.', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding input: {str(e)}', 'error')
            
    return render_template('farm/input_form.html', now=datetime.now())
# --- Finance & Sales Routes ---
@farm_bp.route('/sales/add', methods=['GET', 'POST'])
@login_required
@admin_required
def record_sale():
    # If animal_id is provided via GET, pre-select it
    animal_id = request.args.get('animal_id')
    available_animals = Livestock.query.filter_by(status='Alive').all()
    
    if request.method == 'POST':
        try:
            item_description = request.form.get('item_description')
            amount = float(request.form.get('amount', 0))
            payment_method = request.form.get('payment_method', 'Cash')
            linked_animal_id = request.form.get('animal_id')
            
            # 1. Create Transaction (for general finance tracking)
            new_tx = Transaction(
                amount=amount,
                payment_method=payment_method,
                payment_date=date.today(),
                notes=f"Farm Sale: {item_description}",
                status='Completed',
                department='Farm'
            )
            db.session.add(new_tx)
            
            # 2. Record in Cashbook (Credit)
            new_entry = CashBookEntry(
                date=date.today(),
                description=f"Farm Sale: {item_description}",
                amount=amount,
                type='Credit',
                category='Farm Revenue',
                department='Farm'
            )
            db.session.add(new_entry)
            
            # 3. If an animal was sold, update its status
            if linked_animal_id:
                animal = Livestock.query.get(linked_animal_id)
                if animal:
                    animal.status = 'Sold'
                    animal.notes = (animal.notes or "") + f"\nSold on {date.today()} for MWK {amount}"
            
            db.session.commit()
            flash(f'Sale recorded successfully. Transaction ID: {new_tx.transaction_id}', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording sale: {str(e)}', 'error')
            
    return render_template('farm/sale_form.html', animals=available_animals, pre_selected_animal=animal_id, now=datetime.now())

@farm_bp.route('/receipt/<int:transaction_id>')
@login_required
@admin_required
def generate_receipt(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    try:
        pdf_buffer = generate_receipt_pdf(transaction)
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"Farm_Receipt_{transaction_id}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error generating receipt: {str(e)}', 'error')
        return redirect(url_for('farm.dashboard'))

# --- Asset Inventory Routes ---
@farm_bp.route('/inventory/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_inventory_item():
    if request.method == 'POST':
        try:
            qty = int(request.form.get('quantity', 0))
            val = float(request.form.get('unit_value', 0))
            new_item = Inventory(
                asset_name=request.form.get('asset_name'),
                category=request.form.get('category'),
                subcategory=request.form.get('subcategory'),
                condition=request.form.get('condition'),
                location=request.form.get('location'),
                quantity=qty,
                unit_value=val,
                total_value=qty * val,
                description=request.form.get('description'),
                department='Farm'
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Farm asset added successfully.', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding asset: {str(e)}', 'error')
            
    custom_categories = CustomInventoryCategory.query.filter_by(department='Farm').all()
    return render_template('farm/inventory_form.html', item=None, custom_categories=[c.category_name for c in custom_categories])

@farm_bp.route('/inventory/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_inventory_item(item_id):
    item = Inventory.query.get_or_404(item_id)
    if request.method == 'POST':
        try:
            item.asset_name = request.form.get('asset_name')
            item.category = request.form.get('category')
            item.subcategory = request.form.get('subcategory')
            item.condition = request.form.get('condition')
            item.location = request.form.get('location')
            item.quantity = int(request.form.get('quantity', 0))
            item.unit_value = float(request.form.get('unit_value', 0))
            item.total_value = item.quantity * item.unit_value
            item.description = request.form.get('description')
            db.session.commit()
            flash('Farm asset updated.', 'success')
            return redirect(url_for('farm.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating asset: {str(e)}', 'error')
    custom_categories = CustomInventoryCategory.query.filter_by(department='Farm').all()
    return render_template('farm/inventory_form.html', item=item, custom_categories=[c.category_name for c in custom_categories])

@farm_bp.route('/inventory/delete/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def delete_inventory_item(item_id):
    item = Inventory.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash('Asset deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting asset: {str(e)}', 'error')
    return redirect(url_for('farm.dashboard'))
@farm_bp.route('/api/custom_categories', methods=['POST'])
@login_required
@admin_required
def add_custom_category():
    try:
        data = request.get_json()
        category_name = data.get('category_name')
        department = data.get('department', 'Farm')
        
        if not category_name:
            return jsonify({'success': False, 'message': 'Category name is required'}), 400
            
        existing = CustomInventoryCategory.query.filter_by(category_name=category_name, department=department).first()
        if existing:
            return jsonify({'success': False, 'message': 'Category already exists'}), 400
            
        new_category = CustomInventoryCategory(category_name=category_name, department=department)
        db.session.add(new_category)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Category added successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
