from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from functools import wraps
from models import FarmActivity, FarmInput, FarmOutput, FarmExpense
from db_utils import db
from datetime import datetime

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
    activities = FarmActivity.query.order_by(FarmActivity.start_date.desc()).all()
    
    # Calculate global totals
    total_income = sum(output.total_value for activity in activities for output in activity.outputs)
    total_expense = sum(expense.amount for activity in activities for expense in activity.expenses)
    net_profit = total_income - total_expense
    
    return render_template('farm/dashboard.html', 
                          activities=activities,
                          total_income=total_income,
                          total_expense=total_expense,
                          net_profit=net_profit)

# --- Activity Routes ---
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
                status=status
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
                expense_date=expense_date
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
@farm_bp.route('/activity/<int:activity_id>/input/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_input(activity_id):
    activity = FarmActivity.query.get_or_404(activity_id)
    
    if request.method == 'POST':
        try:
            item_name = request.form.get('item_name')
            category = request.form.get('category')
            quantity = float(request.form.get('quantity', 0))
            unit = request.form.get('unit')
            cost = float(request.form.get('cost', 0))
            
            new_input = FarmInput(
                activity_id=activity.id,
                item_name=item_name,
                category=category,
                quantity=quantity,
                unit=unit,
                cost=cost
            )
            
            db.session.add(new_input)
            
            # Optionally sync input cost to expenses
            sync_expense = request.form.get('sync_expense') == 'yes'
            if sync_expense:
                new_expense = FarmExpense(
                    activity_id=activity.id,
                    expense_category=f"Input: {category}",
                    description=f"Purchase of {quantity} {unit} {item_name}",
                    amount=cost,
                    expense_date=datetime.utcnow().date()
                )
                db.session.add(new_expense)
            
            activity.update_profit()
            db.session.commit()
            
            flash('Input added successfully.', 'success')
            return redirect(url_for('farm.view_activity', activity_id=activity.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding input: {str(e)}', 'error')
            
    return render_template('farm/input_form.html', activity=activity)
