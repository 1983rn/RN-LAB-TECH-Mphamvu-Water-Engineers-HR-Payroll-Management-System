from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Employee, Attendance
from datetime import datetime, date, timedelta
from functools import wraps
import sqlite3

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

WORK_START = "07:30"
WORK_END = "16:00"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def hr_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['Administrator', 'HR Manager']:
            flash('HR access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@attendance_bp.route('/')
@login_required
@hr_required
def dashboard():
    today = date.today()
    filter_date_str = request.args.get('date', today.strftime('%Y-%m-%d'))
    filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
    
    # Run the mark_absentees pass for the specific date if it's today or in the past
    # (Only runs once per day realistically, or catches up)
    if filter_date <= today:
        mark_absentees(filter_date)
    
    records = Attendance.query.filter_by(date=filter_date).order_by(Attendance.employee_id).all()
    
    # Create a mapping for easy templating since records might not have 'employee' pre-joined elegantly if not lazy
    return render_template('attendance/dashboard.html', records=records, filter_date=filter_date_str)

def mark_absentees(target_date):
    """Automatically marks employees as absent if they have no record for the day."""
    active_employees = Employee.query.filter_by(status='Active').all()
    
    for emp in active_employees:
        record = Attendance.query.filter_by(employee_id=emp.employee_id, date=target_date).first()
        if not record:
            # Generate a truly unique reference number
            # Using timestamp plus employee_id to ensure uniqueness in batch operations
            unique_ref = f"ATT{datetime.now().strftime('%Y%m%d%H%M%S')}{emp.employee_id}"
            
            new_record = Attendance(
                employee_id=emp.employee_id,
                date=target_date,
                status='Absent',
                reference_number=unique_ref
            )
            db.session.add(new_record)
            
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error marking absentees: {e}")

@attendance_bp.route('/checkin', methods=['POST'])
@login_required
def manual_checkin():
    employment_number = request.form.get('employment_number')
    if not employment_number:
        flash('Employment Number is required.', 'error')
        return redirect(url_for('attendance.dashboard'))
        
    employee = Employee.query.filter_by(employment_number=employment_number).first()
    if not employee:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.dashboard'))
        
    if process_checkin(employee):
        flash(f'Successfully checked in {employee.first_name} {employee.last_name}', 'success')
    else:
        flash('Check-in failed or already recorded.', 'error')
        
    return redirect(url_for('attendance.dashboard'))

@attendance_bp.route('/checkout', methods=['POST'])
@login_required
def manual_checkout():
    employment_number = request.form.get('employment_number')
    if not employment_number:
        flash('Employment Number is required.', 'error')
        return redirect(url_for('attendance.dashboard'))
        
    employee = Employee.query.filter_by(employment_number=employment_number).first()
    if not employee:
        flash('Employee not found.', 'error')
        return redirect(url_for('attendance.dashboard'))
        
    if process_checkout(employee):
        flash(f'Successfully checked out {employee.first_name} {employee.last_name}', 'success')
    else:
        flash('Check-out failed. Did the employee check in today?', 'error')
        
    return redirect(url_for('attendance.dashboard'))

def process_checkin(employee):
    now = datetime.now()
    today = now.date()
    current_time = now.time()
    
    # Calculate Late Minutes
    start_time = datetime.strptime(WORK_START,"%H:%M").time()
    late_minutes = 0
    if now.hour > start_time.hour or (now.hour == start_time.hour and now.minute > start_time.minute):
        arrival_datetime = datetime.combine(today, current_time)
        start_datetime = datetime.combine(today, start_time)
        late_minutes = int((arrival_datetime - start_datetime).total_seconds() / 60)
    
    # Check for existing record
    record = Attendance.query.filter_by(employee_id=employee.employee_id, date=today).first()
    
    if record:
        if record.check_in:
            return False # Already checked in
        
        # Update existing record (e.g., if marked absent earlier but showed up late)
        record.check_in = current_time
        record.status = 'Late' if late_minutes > 0 else 'Present'
        record.late_minutes = late_minutes
    else:
        # Create new record
        unique_ref = f"ATT{datetime.now().strftime('%Y%m%d%H%M%S')}{employee.employee_id}"
        record = Attendance(
            employee_id=employee.employee_id,
            date=today,
            check_in=current_time,
            status='Late' if late_minutes > 0 else 'Present',
            late_minutes=late_minutes,
            reference_number=unique_ref
        )
        db.session.add(record)
        
    try:
        db.session.commit()
        return True
    except:
        db.session.rollback()
        return False

def process_checkout(employee):
    now = datetime.now()
    today = now.date()
    current_time = now.time()
    
    # Calculate Overtime
    end_time = datetime.strptime(WORK_END,"%H:%M").time()
    overtime_minutes = 0
    
    if now.hour > end_time.hour or (now.hour == end_time.hour and now.minute > end_time.minute):
        leaving_datetime = datetime.combine(today, current_time)
        end_datetime = datetime.combine(today, end_time)
        overtime_minutes = int((leaving_datetime - end_datetime).total_seconds() / 60)
        
    record = Attendance.query.filter_by(employee_id=employee.employee_id, date=today).first()
    
    if record and record.check_in and not record.check_out:
        record.check_out = current_time
        record.overtime_minutes = overtime_minutes
        
        try:
            db.session.commit()
            return True
        except:
            db.session.rollback()
            return False
            
    return False

@attendance_bp.route('/biometric', methods=['GET', 'POST'])
@login_required # Often employees use a shared kiosk, but we'll assume a logged-in HR kiosk or employee portal.
def biometric_checkin():
    if request.method == 'GET':
        return render_template('attendance/biometric.html')
        
    action = request.form.get('action', 'checkin')
    employment_number = request.form.get('employment_number')
    photo_base64 = request.form.get('photo_base64')
    
    if not employment_number or not photo_base64:
        flash('Employment Number and Image are required.', 'error')
        return redirect(url_for('attendance.biometric_checkin'))
        
    employee = Employee.query.filter_by(employment_number=employment_number).first()
    if not employee:
        flash('Invalid Employment Number.', 'error')
        return redirect(url_for('attendance.biometric_checkin'))
        
    # Verify the face utilizing OpenCV cascade fallback
    from utils.biometric_utils import verify_face_in_base64_image, verify_face_match
    is_valid_face, evidence_path = verify_face_in_base64_image(photo_base64)
    
    if not is_valid_face:
        error_msg = (
            "Biometric Verification Failed: No face detected in the frame. <br><br>"
            "<strong>Please:</strong>"
            "<ul>"
            "<li>Look directly at the camera</li>"
            "<li>Ensure you are in a well-lit area</li>"
            "<li>Position your face within the guide box</li>"
            "<li>Remove any hats or sunglasses</li>"
            "</ul>"
        )
        flash(error_msg, 'error')
        return redirect(url_for('attendance.biometric_checkin'))
        
    # Optional: Verify face match against stored photo if employee has one
    if employee.photo_path:
        # Assuming photo_path is relative to static or absolute
        import os
        photo_full_path = employee.photo_path
        if not os.path.isabs(photo_full_path):
            photo_full_path = os.path.join('static', employee.photo_path)
            
        if os.path.exists(photo_full_path):
            if not verify_face_match(evidence_path, photo_full_path):
                flash("Biometric verification failed: Face does not match our records. Please contact HR.", 'error')
                return redirect(url_for('attendance.biometric_checkin'))
        
    if action == 'checkin':
        if process_checkin(employee):
            flash(f'Check-In successful for {employee.first_name}. Evidence saved.', 'success')
        else:
            flash(f'Check-In failed. Have you already checked in today?', 'error')
    else:
        if process_checkout(employee):
            flash(f'Check-Out successful for {employee.first_name}. Evidence saved.', 'success')
        else:
            flash(f'Check-Out failed. Please check in first.', 'error')
            
    return redirect(url_for('attendance.biometric_checkin'))

# --- Multi-Employee AI Recognition Routes ---

from utils.biometric_utils import MultiFaceRecognizer
import cv2
from flask import Response
import time

# Initialize global recognizer
recognizer = MultiFaceRecognizer()

@attendance_bp.route('/live_kiosk')
@login_required 
def live_kiosk():
    # Refresh known faces from DB on each page load/start
    recognizer.load_known_faces()
    return render_template('attendance/live_kiosk.html')

def gen_frames():
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Could not open camera")
        return

    while True:
        success, frame = camera.read()
        if not success:
            break
        
        # Process frame with Multi-Face Recognizer
        processed_frame, detected_employees = recognizer.process_frame(frame)
        
        # Mark attendance for detected employees
        from models import Employee
        for emp_data in detected_employees:
            emp_id = emp_data['id']
            
            # Check if already marked in this session or cooldown
            now_ts = time.time()
            if emp_id not in recognizer.last_marked or (now_ts - recognizer.last_marked[emp_id]) > recognizer.cooldown_seconds:
                employee = Employee.query.get(emp_id)
                if employee:
                    if process_checkin(employee):
                        recognizer.last_marked[emp_id] = now_ts
                        print(f"AUTOMATIC ATTENDANCE: {emp_data['name']} marked.")
        
        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', processed_frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    camera.release()

@attendance_bp.route('/video_feed')
@login_required
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
