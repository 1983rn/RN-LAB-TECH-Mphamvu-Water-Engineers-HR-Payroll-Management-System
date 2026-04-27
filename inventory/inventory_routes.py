from flask import Blueprint, render_template, request, flash, redirect, url_for, session, Response, jsonify
from functools import wraps
from utils.auth_utils import apply_dept_filter, get_current_dept
from models import Inventory, CustomInventoryCategory
from db_utils import db
import csv
import io

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

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

@inventory_bp.route('/', methods=['GET'])
@inventory_bp.route('/dashboard', methods=['GET'])
@login_required
@admin_required
def dashboard():
    query = Inventory.query
    items = apply_dept_filter(query, Inventory).all()
    
    total_value = sum(item.total_value for item in items)
    total_items = sum(item.quantity for item in items)
    
    # Categories counts & values
    categories = {}
    good_condition_count = 0
    
    for item in items:
        if item.category not in categories:
            categories[item.category] = {'count': 0, 'value': 0}
        categories[item.category]['count'] += item.quantity
        categories[item.category]['value'] += item.total_value
        
        if item.condition in ['New', 'Excellent', 'Good']:
            good_condition_count += item.quantity
            
    good_condition_pct = (good_condition_count / total_items * 100) if total_items > 0 else 0
    
    return render_template('inventory/dashboard.html',
                           total_value=total_value,
                           total_items=total_items,
                           categories=categories,
                           good_condition_pct=good_condition_pct)

@inventory_bp.route('/category/<string:category>', methods=['GET'])
@login_required
@admin_required
def category_view(category):
    query = Inventory.query.filter_by(category=category)
    items = apply_dept_filter(query, Inventory).order_by(Inventory.subcategory, Inventory.asset_name).all()
    
    total_value = sum(item.total_value for item in items)
    line_items = len(items)
    
    subcategories = {}
    for item in items:
        subcat = item.subcategory or 'Uncategorized'
        if subcat not in subcategories:
            subcategories[subcat] = {'items': [], 'total': 0}
        subcategories[subcat]['items'].append(item)
        subcategories[subcat]['total'] += item.total_value

    return render_template('inventory/category.html',
                           category_name=category,
                           total_value=total_value,
                           line_items=line_items,
                           subcategories=subcategories)

@inventory_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_item():
    if request.method == 'POST':
        try:
            asset_name = request.form.get('asset_name')
            category = request.form.get('category')
            subcategory = request.form.get('subcategory')
            condition = request.form.get('condition')
            location = request.form.get('location')
            quantity = int(request.form.get('quantity', 0))
            unit_value = float(request.form.get('unit_value', 0))
            description = request.form.get('description')
            
            total_value = quantity * unit_value
            
            new_item = Inventory(
                asset_name=asset_name,
                category=category,
                subcategory=subcategory,
                condition=condition,
                location=location,
                quantity=quantity,
                unit_value=unit_value,
                total_value=total_value,
                description=description,
                department=get_current_dept()
            )
            
            db.session.add(new_item)
            db.session.commit()
            
            flash('Inventory item added successfully.', 'success')
            return redirect(url_for('inventory.category_view', category=category))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding item: {str(e)}', 'error')
            
    dept = get_current_dept()
    custom_categories = CustomInventoryCategory.query.filter_by(department=dept).all()
    return render_template('inventory/form.html', item=None, dept_context=dept, custom_categories=[c.category_name for c in custom_categories])

@inventory_bp.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_item(item_id):
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
            item.description = request.form.get('description')
            
            item.total_value = item.quantity * item.unit_value
            
            db.session.commit()
            
            flash('Inventory item updated successfully.', 'success')
            return redirect(url_for('inventory.category_view', category=item.category))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating item: {str(e)}', 'error')
            
    dept = get_current_dept()
    custom_categories = CustomInventoryCategory.query.filter_by(department=dept).all()
    return render_template('inventory/form.html', item=item, dept_context=dept, custom_categories=[c.category_name for c in custom_categories])

@inventory_bp.route('/delete/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def delete_item(item_id):
    item = Inventory.query.get_or_404(item_id)
    category = item.category
    try:
        db.session.delete(item)
        db.session.commit()
        flash('Inventory item deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting item: {str(e)}', 'error')
        
    return redirect(url_for('inventory.category_view', category=category))

@inventory_bp.route('/export/<string:category>', methods=['GET'])
@login_required
@admin_required
def export_csv(category):
    query = Inventory.query.filter_by(category=category)
    items = apply_dept_filter(query, Inventory).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Asset Name', 'Subcategory', 'Quantity', 'Unit Value (MWK)', 'Total Value (MWK)', 'Condition', 'Location', 'Description'])
    
    for item in items:
        writer.writerow([
            item.id,
            item.asset_name,
            item.subcategory or 'N/A',
            item.quantity,
            "{:.2f}".format(item.unit_value),
            "{:.2f}".format(item.total_value),
            item.condition or 'Good',
            item.location or 'N/A',
            item.description or ''
        ])
    
    output.seek(0)
    
    filename = f"inventory_{category.replace(' ', '_').lower()}.csv"
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@inventory_bp.route('/fix-departments', methods=['POST'])
@login_required
@admin_required
def fix_departments():
    """
    Utility route to departmentalize existing inventory items based on their category.
    """
    items = Inventory.query.all()
    count = 0
    for item in items:
        old_dept = item.department
        new_dept = old_dept
        
        cat = item.category or ""
        name = item.asset_name or ""
        
        # 1. Farm
        if any(cat.startswith(str(i) + ".") for i in range(1, 9)) or \
           any(term in cat.lower() for term in ['farm', 'crop', 'livestock', 'harvest']):
            new_dept = 'Farm'
        # 2. ICT
        elif 'ICT' in cat.upper() or 'ICT' in name.upper() or 'SOFTWARE' in cat.upper():
            new_dept = 'ICT Department'
        # 3. Borehole
        elif 'BOREHOLE' in cat.upper() or 'DRILLING' in cat.upper():
            new_dept = 'Borehole Drilling'
        # 4. Construction
        elif 'CONSTRUCTION' in cat.upper() or 'BUILDING' in cat.upper():
            new_dept = 'Construction'
        # 5. Lodge
        elif 'LODGE' in cat.upper() or 'ROOM' in cat.upper() or 'BED' in cat.upper():
            new_dept = 'Lodge'
            
        if not new_dept:
            new_dept = 'Borehole Drilling' # Default fallback
            
        if old_dept != new_dept:
            item.department = new_dept
            count += 1
            
    db.session.commit()
    flash(f'Departmentalized {count} inventory items successfully.', 'success')
    return redirect(url_for('inventory.dashboard'))
