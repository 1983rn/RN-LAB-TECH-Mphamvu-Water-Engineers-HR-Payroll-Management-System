from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps
from models import (
    LodgeRoom, LodgeBooking, LodgeCustomer,
    LodgePayment, LodgeExpense, LodgeInventory
)
from db_utils import db
from datetime import datetime, date

rest_house_bp = Blueprint('rest_house', __name__, url_prefix='/rest-house')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ─── DASHBOARD ────────────────────────────────────────────
@rest_house_bp.route('/')
@login_required
def dashboard():
    session['department_context'] = 'Lodge'
    session['department_dashboard'] = 'rest_house.dashboard'

    # Gather stats
    total_rooms = LodgeRoom.query.count()
    available_rooms = LodgeRoom.query.filter_by(status='Available').count()
    occupied_rooms = LodgeRoom.query.filter_by(status='Occupied').count()
    total_bookings = LodgeBooking.query.count()
    active_bookings = LodgeBooking.query.filter(LodgeBooking.status.in_(['Confirmed', 'Checked-In'])).count()
    total_customers = LodgeCustomer.query.count()

    # Financial stats
    total_revenue = db.session.query(db.func.sum(LodgePayment.amount)).filter_by(status='Completed').scalar() or 0
    total_expenses = db.session.query(db.func.sum(LodgeExpense.amount)).scalar() or 0
    inventory_value = db.session.query(db.func.sum(LodgeInventory.total_value)).scalar() or 0

    return render_template('rest_house/dashboard.html',
                           total_rooms=total_rooms,
                           available_rooms=available_rooms,
                           occupied_rooms=occupied_rooms,
                           total_bookings=total_bookings,
                           active_bookings=active_bookings,
                           total_customers=total_customers,
                           total_revenue=total_revenue,
                           total_expenses=total_expenses,
                           inventory_value=inventory_value,
                           now=datetime.now())

# ─── ROOMS ────────────────────────────────────────────────
@rest_house_bp.route('/rooms', methods=['GET', 'POST'])
@login_required
def rooms():
    if request.method == 'POST':
        try:
            room = LodgeRoom(
                room_number=request.form['room_number'],
                room_type=request.form['room_type'],
                price_per_night=float(request.form.get('price_per_night', 0)),
                status=request.form.get('status', 'Available'),
                amenities=request.form.get('amenities', ''),
                description=request.form.get('description', ''),
                floor=request.form.get('floor', ''),
                max_guests=int(request.form.get('max_guests', 2))
            )
            db.session.add(room)
            db.session.commit()
            flash('Room added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding room: {str(e)}', 'error')
        return redirect(url_for('rest_house.rooms'))

    rooms_list = LodgeRoom.query.order_by(LodgeRoom.room_number).all()
    return render_template('rest_house/rooms.html', rooms=rooms_list)

@rest_house_bp.route('/rooms/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(id):
    room = LodgeRoom.query.get_or_404(id)
    if request.method == 'POST':
        try:
            room.room_number = request.form['room_number']
            room.room_type = request.form['room_type']
            room.price_per_night = float(request.form.get('price_per_night', 0))
            room.status = request.form.get('status', 'Available')
            room.amenities = request.form.get('amenities', '')
            room.description = request.form.get('description', '')
            room.floor = request.form.get('floor', '')
            room.max_guests = int(request.form.get('max_guests', 2))
            db.session.commit()
            flash('Room updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating room: {str(e)}', 'error')
        return redirect(url_for('rest_house.rooms'))
    return render_template('rest_house/rooms.html', rooms=LodgeRoom.query.all(), edit_room=room)

@rest_house_bp.route('/rooms/<int:id>/delete', methods=['POST'])
@login_required
def delete_room(id):
    room = LodgeRoom.query.get_or_404(id)
    try:
        db.session.delete(room)
        db.session.commit()
        flash('Room deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting room: {str(e)}', 'error')
    return redirect(url_for('rest_house.rooms'))

# ─── CUSTOMERS ────────────────────────────────────────────
@rest_house_bp.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        try:
            customer = LodgeCustomer(
                full_name=request.form['full_name'],
                phone=request.form.get('phone', ''),
                email=request.form.get('email', ''),
                id_number=request.form.get('id_number', ''),
                nationality=request.form.get('nationality', 'Malawian'),
                address=request.form.get('address', ''),
                notes=request.form.get('notes', '')
            )
            db.session.add(customer)
            db.session.commit()
            flash('Customer added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding customer: {str(e)}', 'error')
        return redirect(url_for('rest_house.customers'))

    customers_list = LodgeCustomer.query.order_by(LodgeCustomer.created_at.desc()).all()
    return render_template('rest_house/customers.html', customers=customers_list)

@rest_house_bp.route('/customers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = LodgeCustomer.query.get_or_404(id)
    if request.method == 'POST':
        try:
            customer.full_name = request.form['full_name']
            customer.phone = request.form.get('phone', '')
            customer.email = request.form.get('email', '')
            customer.id_number = request.form.get('id_number', '')
            customer.nationality = request.form.get('nationality', 'Malawian')
            customer.address = request.form.get('address', '')
            customer.notes = request.form.get('notes', '')
            db.session.commit()
            flash('Customer updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating customer: {str(e)}', 'error')
        return redirect(url_for('rest_house.customers'))
    return render_template('rest_house/customers.html',
                           customers=LodgeCustomer.query.all(), edit_customer=customer)

@rest_house_bp.route('/customers/<int:id>/delete', methods=['POST'])
@login_required
def delete_customer(id):
    customer = LodgeCustomer.query.get_or_404(id)
    try:
        db.session.delete(customer)
        db.session.commit()
        flash('Customer deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting customer: {str(e)}', 'error')
    return redirect(url_for('rest_house.customers'))

# ─── BOOKINGS ─────────────────────────────────────────────
@rest_house_bp.route('/bookings', methods=['GET', 'POST'])
@login_required
def bookings():
    if request.method == 'POST':
        try:
            room = LodgeRoom.query.get(int(request.form['room_id']))
            check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
            check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
            nights = (check_out - check_in).days
            total = nights * room.price_per_night if room and nights > 0 else 0

            booking = LodgeBooking(
                customer_id=int(request.form['customer_id']),
                room_id=int(request.form['room_id']),
                check_in=check_in,
                check_out=check_out,
                num_guests=int(request.form.get('num_guests', 1)),
                total_amount=total,
                status=request.form.get('status', 'Confirmed'),
                notes=request.form.get('notes', '')
            )
            db.session.add(booking)

            # Mark room as occupied if checked-in
            if booking.status == 'Checked-In' and room:
                room.status = 'Occupied'

            db.session.commit()
            flash('Booking created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating booking: {str(e)}', 'error')
        return redirect(url_for('rest_house.bookings'))

    bookings_list = LodgeBooking.query.order_by(LodgeBooking.created_at.desc()).all()
    rooms_list = LodgeRoom.query.order_by(LodgeRoom.room_number).all()
    customers_list = LodgeCustomer.query.order_by(LodgeCustomer.full_name).all()
    return render_template('rest_house/bookings.html',
                           bookings=bookings_list, rooms=rooms_list, customers=customers_list)

@rest_house_bp.route('/bookings/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_booking(id):
    booking = LodgeBooking.query.get_or_404(id)
    if request.method == 'POST':
        try:
            old_room = LodgeRoom.query.get(booking.room_id)
            new_room = LodgeRoom.query.get(int(request.form['room_id']))

            booking.customer_id = int(request.form['customer_id'])
            booking.room_id = int(request.form['room_id'])
            booking.check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
            booking.check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
            booking.num_guests = int(request.form.get('num_guests', 1))
            booking.status = request.form.get('status', 'Confirmed')
            booking.notes = request.form.get('notes', '')

            nights = (booking.check_out - booking.check_in).days
            booking.total_amount = nights * new_room.price_per_night if new_room and nights > 0 else 0

            # Update room statuses
            if booking.status == 'Checked-Out' or booking.status == 'Cancelled':
                if new_room:
                    new_room.status = 'Available'
            elif booking.status == 'Checked-In':
                if new_room:
                    new_room.status = 'Occupied'

            if old_room and old_room.id != new_room.id:
                old_room.status = 'Available'

            db.session.commit()
            flash('Booking updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating booking: {str(e)}', 'error')
        return redirect(url_for('rest_house.bookings'))

    bookings_list = LodgeBooking.query.order_by(LodgeBooking.created_at.desc()).all()
    rooms_list = LodgeRoom.query.order_by(LodgeRoom.room_number).all()
    customers_list = LodgeCustomer.query.order_by(LodgeCustomer.full_name).all()
    return render_template('rest_house/bookings.html',
                           bookings=bookings_list, rooms=rooms_list,
                           customers=customers_list, edit_booking=booking)

# ─── PAYMENTS ─────────────────────────────────────────────
@rest_house_bp.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    if request.method == 'POST':
        try:
            payment = LodgePayment(
                booking_id=int(request.form['booking_id']),
                amount=float(request.form['amount']),
                payment_method=request.form.get('payment_method', 'Cash'),
                payment_date=datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date(),
                reference=request.form.get('reference', ''),
                status=request.form.get('status', 'Completed'),
                notes=request.form.get('notes', '')
            )
            db.session.add(payment)
            db.session.commit()
            flash('Payment recorded successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'error')
        return redirect(url_for('rest_house.payments'))

    payments_list = LodgePayment.query.order_by(LodgePayment.payment_date.desc()).all()
    bookings_list = LodgeBooking.query.order_by(LodgeBooking.created_at.desc()).all()
    total_payments = sum(p.amount for p in payments_list if p.status == 'Completed')
    return render_template('rest_house/payments.html',
                           payments=payments_list, bookings=bookings_list,
                           total_payments=total_payments)

# ─── EXPENSES ─────────────────────────────────────────────
@rest_house_bp.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        try:
            expense = LodgeExpense(
                description=request.form['description'],
                category=request.form.get('category', 'Operations'),
                amount=float(request.form['amount']),
                expense_date=datetime.strptime(request.form['expense_date'], '%Y-%m-%d').date(),
                reference=request.form.get('reference', ''),
                notes=request.form.get('notes', '')
            )
            db.session.add(expense)
            db.session.commit()
            flash('Expense recorded successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording expense: {str(e)}', 'error')
        return redirect(url_for('rest_house.expenses'))

    expenses_list = LodgeExpense.query.order_by(LodgeExpense.expense_date.desc()).all()
    total_expenses = sum(e.amount for e in expenses_list)

    # Category breakdown
    category_totals = {}
    for e in expenses_list:
        cat = e.category or 'Other'
        category_totals[cat] = category_totals.get(cat, 0) + e.amount

    return render_template('rest_house/expenses.html',
                           expenses=expenses_list, total_expenses=total_expenses,
                           category_totals=category_totals)

# ─── INVENTORY ────────────────────────────────────────────
@rest_house_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        try:
            qty = int(request.form.get('quantity', 0))
            unit_val = float(request.form.get('unit_value', 0))
            item = LodgeInventory(
                item_name=request.form['item_name'],
                category=request.form.get('category', 'Furniture'),
                quantity=qty,
                unit_value=unit_val,
                total_value=qty * unit_val,
                condition=request.form.get('condition', 'Good'),
                location=request.form.get('location', ''),
                description=request.form.get('description', '')
            )
            db.session.add(item)
            db.session.commit()
            flash('Inventory item added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding inventory item: {str(e)}', 'error')
        return redirect(url_for('rest_house.inventory'))

    items = LodgeInventory.query.order_by(LodgeInventory.category, LodgeInventory.item_name).all()
    total_value = sum(i.total_value for i in items)

    # Category breakdown
    category_totals = {}
    for item in items:
        cat = item.category
        if cat not in category_totals:
            category_totals[cat] = {'count': 0, 'value': 0}
        category_totals[cat]['count'] += item.quantity
        category_totals[cat]['value'] += item.total_value

    return render_template('rest_house/lodge_inventory.html',
                           items=items, total_value=total_value,
                           category_totals=category_totals)

@rest_house_bp.route('/inventory/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_inventory(id):
    item = LodgeInventory.query.get_or_404(id)
    if request.method == 'POST':
        try:
            item.item_name = request.form['item_name']
            item.category = request.form.get('category', 'Furniture')
            item.quantity = int(request.form.get('quantity', 0))
            item.unit_value = float(request.form.get('unit_value', 0))
            item.total_value = item.quantity * item.unit_value
            item.condition = request.form.get('condition', 'Good')
            item.location = request.form.get('location', '')
            item.description = request.form.get('description', '')
            db.session.commit()
            flash('Inventory item updated!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating item: {str(e)}', 'error')
        return redirect(url_for('rest_house.inventory'))

    items = LodgeInventory.query.order_by(LodgeInventory.category).all()
    total_value = sum(i.total_value for i in items)
    category_totals = {}
    for i in items:
        cat = i.category
        if cat not in category_totals:
            category_totals[cat] = {'count': 0, 'value': 0}
        category_totals[cat]['count'] += i.quantity
        category_totals[cat]['value'] += i.total_value

    return render_template('rest_house/lodge_inventory.html',
                           items=items, total_value=total_value,
                           category_totals=category_totals, edit_item=item)

@rest_house_bp.route('/inventory/<int:id>/delete', methods=['POST'])
@login_required
def delete_inventory(id):
    item = LodgeInventory.query.get_or_404(id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash('Inventory item deleted!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('rest_house.inventory'))

# ─── CASH BOOK ────────────────────────────────────────────
@rest_house_bp.route('/cashbook')
@login_required
def cashbook():
    # Credits = Payments received
    payments = LodgePayment.query.filter_by(status='Completed').order_by(LodgePayment.payment_date.desc()).all()
    credits_list = []
    for p in payments:
        customer_name = p.booking.customer.full_name if p.booking and p.booking.customer else 'Unknown'
        room_no = p.booking.room.room_number if p.booking and p.booking.room else 'N/A'
        credits_list.append({
            'date': p.payment_date,
            'description': f"Room {room_no} - {customer_name}",
            'ref': p.reference or p.payment_method,
            'amount': float(p.amount),
            'category': p.payment_method
        })

    # Debits = Expenses
    expenses = LodgeExpense.query.order_by(LodgeExpense.expense_date.desc()).all()
    debits_list = []
    for e in expenses:
        debits_list.append({
            'date': e.expense_date,
            'description': e.description,
            'ref': e.reference or 'Lodge',
            'amount': float(e.amount),
            'category': e.category or 'Operations'
        })

    total_income = sum(c['amount'] for c in credits_list)
    total_debits = sum(d['amount'] for d in debits_list)
    balance = total_income - total_debits

    # Breakdowns
    income_breakdown = {}
    for c in credits_list:
        cat = c['category']
        income_breakdown[cat] = income_breakdown.get(cat, 0) + c['amount']

    expense_breakdown = {}
    for d in debits_list:
        cat = d['category']
        expense_breakdown[cat] = expense_breakdown.get(cat, 0) + d['amount']

    return render_template('rest_house/cashbook.html',
                           credits=credits_list,
                           debits=debits_list,
                           total_income=total_income,
                           total_debits=total_debits,
                           balance=balance,
                           income_breakdown=income_breakdown,
                           expense_breakdown=expense_breakdown,
                           now=datetime.now())

# ─── EXIT DEPARTMENT ──────────────────────────────────────
@rest_house_bp.route('/exit')
@login_required
def exit_department():
    session.pop('department_context', None)
    session.pop('department_dashboard', None)
    return redirect(url_for('dashboard'))
