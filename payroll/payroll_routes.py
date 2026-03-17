from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from models import db, Employee, Payroll, EmployeeLoan, Attendance
from datetime import datetime, date
from functools import wraps
import io
import re
from collections import defaultdict
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from utils.pdf_utils import add_company_header_to_story, add_pdf_footer, add_signature_block, build_pdf_with_numbering, create_numbered_doc, generate_document_number, generate_qr_code, add_stamp_and_qr, generate_document_hash, secure_pdf, add_hash_to_story

payroll_bp = Blueprint('payroll', __name__, url_prefix='/payroll')

def clean_filename(text):
    """Sanitize text for safe use in filenames."""
    return re.sub(r'[^A-Za-z0-9_]', '_', text)

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

def calculate_payee_tax(gross_salary):
    """Calculates Malawi PAYE Tax based on flat-rate brackets.
    
    Brackets:
      150,000 - 170,000   → 0%
      170,001 - 1,570,000 → 30% of entire gross
      1,570,001 - 10,000,000 → 35% of entire gross
      Outside range → 0%
    """
    if 150000 <= gross_salary <= 170000:
        return 0
    elif 170001 <= gross_salary <= 1570000:
        return round(gross_salary * 0.30, 2)
    elif 1570001 <= gross_salary <= 10000000:
        return round(gross_salary * 0.35, 2)
    else:
        return 0

def calculate_monthly_loan(loan_amount, months):
    """Calculates monthly loan deduction strictly as per directive."""
    if months <= 0: return 0
    monthly_payment = loan_amount / months
    return round(monthly_payment, 2)

def get_employee_loan_deductions(employee_id):
    """Fetches total monthly loan deductions for an employee."""
    # Directive suggests finding active loans and deducting monthly amount
    loan = EmployeeLoan.query.filter_by(employee_id=employee_id, status='Active').first()
    return loan.monthly_deduction if loan else 0.0

def get_absentee_deduction(employee, payroll_month, gross_salary=None):
    """Calculates deduction based on 'Absent' records for a specific month.
    Formula: Gross Salary / 30 * number of absent days.
    """
    try:
        year, month = payroll_month.split('-')
        absent_records_count = Attendance.query.filter(
            Attendance.employee_id == employee.employee_id,
            Attendance.status == 'Absent',
            db.extract('year', Attendance.date) == int(year),
            db.extract('month', Attendance.date) == int(month)
        ).count()
        
        # Use provided gross_salary or fallback to basic employee.salary
        salary_basis = gross_salary if gross_salary is not None else employee.salary
        daily_salary = salary_basis / 30
        return round(absent_records_count * daily_salary, 2), absent_records_count
    except:
        return 0.0, 0

@payroll_bp.route('/')
@login_required
@hr_required
def payroll_list():
    payroll_records = Payroll.query.order_by(Payroll.created_at.desc()).all()
    return render_template('payroll/list.html', payroll_records=payroll_records)

@payroll_bp.route('/process', methods=['GET', 'POST'])
@login_required
@hr_required
def process_payroll():
    if request.method == 'POST':
        try:
            employee_id = request.form['employee_id']
            employee = Employee.query.get_or_404(employee_id)
            
            # Validate employee is active
            if employee.status != 'Active':
                flash(f'Cannot process payroll. Employee {employee.first_name} {employee.last_name} is not active (Status: {employee.status})', 'error')
                return redirect(url_for('payroll.process_payroll'))
            
            payroll_month = request.form['payroll_month']
            basic_salary = float(request.form['basic_salary'])
            allowances = float(request.form.get('allowances', 0))
            
            # Fetch automatic deductions
            
            # Absentee check for the given month
            absentee_deduction, absent_records_count = get_absentee_deduction(employee, payroll_month)
            
            if absent_records_count > 0:
                flash(f'Employee had {absent_records_count} absent day(s) detected. Deducting MK {"{:,.2f}".format(absentee_deduction)}', 'warning')

            loan_deduction = get_employee_loan_deductions(employee_id)
            
            # Other Manual Deductions
            manual_deductions = float(request.form.get('deductions', 0))
            
            # Payee tax
            payee_override = 'payee_override' in request.form
            gross_salary = basic_salary + allowances
            payee_tax = float(request.form.get('taxes', 0)) if payee_override else calculate_payee_tax(gross_salary)
            
            # Total Deductions for NET calculation
            # User wants 4 categories: PAYEE, Loans, Absenteeism, Other
            absentee_deduction_val = float(request.form.get('absentee_deduction', 0))
            loan_deduction_val = float(request.form.get('loan_deduction', 0))
            manual_deductions = float(request.form.get('deductions', 0))
            
            total_deductions = payee_tax + loan_deduction_val + manual_deductions + absentee_deduction_val
            
            # Use basic_salary + allowances for payroll object
            # Validate total deductions don't exceed gross salary
            gross_salary = basic_salary + allowances
            if total_deductions > gross_salary:
                flash('Total deductions cannot exceed gross salary', 'error')
                return redirect(url_for('payroll.process_payroll'))
            
            # Update Loan Balance if deduction exists
            if loan_deduction_val > 0:
                loan = EmployeeLoan.query.filter_by(employee_id=employee_id, status='Active').first()
                if loan:
                    loan.amount_paid += loan_deduction_val
                    loan.balance -= loan_deduction_val
                    if loan.balance <= 0:
                        loan.balance = 0
                        loan.status = 'Paid'
            
            # Calculate net salary
            net_salary = gross_salary - total_deductions
            
            payroll = Payroll(
                employee_id=employee_id,
                payroll_month=payroll_month,
                basic_salary=basic_salary,
                allowances=allowances,
                payee_tax=payee_tax,
                loan_deduction=loan_deduction,
                deductions=manual_deductions,
                absentee_deduction=absentee_deduction_val,
                taxes=payee_tax,
                net_salary=net_salary,
                status='Processed'
            )
            
            db.session.add(payroll)
            db.session.commit()
            
            flash(f'Payroll processed for {payroll.employee.first_name} {payroll.employee.last_name}', 'success')
            return redirect(url_for('payroll.payroll_list'))
            
        except Exception as e:
            flash(f'Error processing payroll: {str(e)}', 'error')
            return redirect(url_for('payroll.process_payroll'))
    
    employees = Employee.query.filter_by(status='Active').all()
    
    # Pre-calculate data for each employee to help frontend (optional enhancement)
    employee_data = []
    for emp in employees:
        employee_data.append({
            'id': emp.employee_id,
            'salary': emp.salary,
            'loans': get_employee_loan_deductions(emp.employee_id)
        })
        
    return render_template('payroll/process.html', employees=employees, employee_data=employee_data)

@payroll_bp.route('/get_employee_deductions/<int:employee_id>/<month>')
@login_required
@hr_required
def get_employee_deductions(employee_id, month):
    """API endpoint to fetch real-time deduction data for frontend."""
    from flask import jsonify
    employee = Employee.query.get_or_404(employee_id)
    
    # Allowances might be passed optionally if we want real-time Gross based penalty
    allowances = float(request.args.get('allowances', 0))
    gross_salary = employee.salary + allowances
    
    loan_deduction = get_employee_loan_deductions(employee_id)
    absent_penalty, absent_count = get_absentee_deduction(employee, month, gross_salary=gross_salary)
    
    return jsonify({
        'loan_deduction': loan_deduction,
        'absentee_deduction': absent_penalty,
        'absentee_count': absent_count,
        'basic_salary': employee.salary
    })

@payroll_bp.route('/payslip/<int:payroll_id>')
@login_required
def view_payslip(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    
    # Check if employee is viewing their own payslip or if user has HR access
    if session.get('role') not in ['Administrator', 'HR Manager']:
        # Need to check if this employee owns this payslip
        # This would require linking users to employees in a real system
        pass
    
    return render_template('payroll/payslip.html', payroll=payroll)

@payroll_bp.route('/payslip/pdf/<int:payroll_id>')
@login_required
def download_payslip_pdf(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    employee = payroll.employee
    
    # Static for payslips:
    layout_mode = "normal"
    
    # Create PDF
    buffer = io.BytesIO()
    doc = create_numbered_doc(buffer, pagesize=A4, rightMargin=51, leftMargin=51, topMargin=40, bottomMargin=50)
    story = []
    
    col_padding = 4 if layout_mode == 'normal' else (2 if layout_mode == 'compact' else 1)
    font_size = 12 if layout_mode == 'normal' else (11.5 if layout_mode == 'compact' else 11)
    
    # Generate official payslip number
    payslip_number = generate_document_number('PAY', payroll.payroll_id, payroll.created_at)
    
    # Generate document hash
    doc_hash = generate_document_hash(payslip_number, f"{employee.first_name} {employee.last_name}", payroll.net_salary)
    
    # Generate QR code
    qr_path = generate_qr_code('Payslip', payslip_number, f"{employee.first_name} {employee.last_name}", payroll.net_salary)
    
    # Add company header
    story = add_company_header_to_story(story, layout_mode=layout_mode)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=10,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    # Payslip Title with number
    story.append(Paragraph(f"PAYSLIP - {payslip_number}", title_style))
    story.append(Spacer(1, 8))
    
    # Employee Information
    employee_data = [
        ['Employee Name:', f"{employee.first_name} {employee.last_name}"],
        ['Employment Number:', employee.employment_number],
        ['Department:', employee.department],
        ['Position:', employee.position],
        ['Payroll Month:', payroll.payroll_month],
    ]
    
    employee_table = Table(employee_data, colWidths=[2*inch, 4*inch])
    employee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
    ]))
    
    story.append(employee_table)
    story.append(Spacer(1, 8))
    
    # Salary Breakdown
    salary_data = [
        ['Description', 'Amount (MWK)'],
        ['Basic Salary', f"{payroll.basic_salary:,.2f}"],
        ['Allowances', f"{payroll.allowances:,.2f}"],
        ['Gross Salary', f"{payroll.basic_salary + payroll.allowances:,.2f}"],
        ['PAYEE Tax', f"-{payroll.payee_tax:,.2f}"],
        ['Loan Repayments', f"-{payroll.loan_deduction:,.2f}"],
        ['Absenteeism Penalty', f"-{payroll.absentee_deduction:,.2f}"],
        ['Other Deductions', f"-{payroll.deductions:,.2f}"],
        ['NET SALARY', f"{payroll.net_salary:,.2f}"],
    ]
    
    salary_table = Table(salary_data, colWidths=[3*inch, 2*inch])
    salary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
        ('BACKGROUND', (0, 6), (-1, 6), colors.lightblue),
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 7), (-1, 7), 14),
    ]))
    
    story.append(salary_table)
    story.append(Spacer(1, 10))
    
    # Footer
    story.append(Paragraph("This is a computer-generated payslip", styles['Normal']))
    
    # Add signature block
    story = add_signature_block(story, layout_mode=layout_mode)
    
    # Add stamp and QR code
    story = add_stamp_and_qr(story, payslip_number, qr_path)
    
    # Add verification hash
    story = add_hash_to_story(story, doc_hash)
    
    # Add developer footer
    story = add_pdf_footer(story, layout_mode=layout_mode)
    
    # Build PDF with numbering
    build_pdf_with_numbering(doc, story)
    
    # Secure the PDF
    buffer.seek(0)
    secured_buffer = secure_pdf(buffer)
    
    secured_buffer.seek(0)
    response = make_response(secured_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    # Format filename with employee name and month
    emp_name = clean_filename(f"{employee.first_name}_{employee.last_name}")
    try:
        month_date = datetime.strptime(payroll.payroll_month, '%Y-%m')
        month_str = month_date.strftime('%B_%Y')
    except:
        month_str = payroll.payroll_month
    response.headers['Content-Disposition'] = f'attachment; filename=Payslip_{emp_name}_{month_str}.pdf'
    
    return response

@payroll_bp.route('/loans')
@login_required
@hr_required
def loan_management():
    employees = Employee.query.filter_by(status='Active').all()
    loans = EmployeeLoan.query.order_by(EmployeeLoan.id.desc()).all()
    return render_template('payroll/loans.html', employees=employees, loans=loans)

@payroll_bp.route('/loans/add', methods=['POST'])
@login_required
@hr_required
def add_loan():
    try:
        employee_id = request.form['employee_id']
        employee = Employee.query.get_or_404(employee_id)
        
        loan_amount = float(request.form['loan_amount'])
        repayment_months = int(request.form['repayment_months'])
        
        # Apply 5% interest
        interest_rate = 0.05
        interest = loan_amount * interest_rate
        total_payable = loan_amount + interest
        
        monthly_deduction = calculate_monthly_loan(total_payable, repayment_months)
        
        loan = EmployeeLoan(
            employee_id=employee_id,
            employment_no=employee.employment_number,
            loan_amount=loan_amount,
            repayment_months=repayment_months,
            monthly_deduction=monthly_deduction,
            amount_paid=0,
            balance=total_payable,
            start_date=date.today().strftime('%Y-%m-%d'),
            status='Active'
        )
        
        db.session.add(loan)
        db.session.commit()
        
        flash(f'Loan of MK {loan_amount:,.2f} + 5% interest (MK {interest:,.2f}) = MK {total_payable:,.2f} registered for {employee.first_name} {employee.last_name}', 'success')
    except Exception as e:
        flash(f'Error adding loan: {str(e)}', 'error')
    
    return redirect(url_for('payroll.loan_management'))


@payroll_bp.route('/report/<month>')
@login_required
@hr_required
def download_payroll_report(month):
    """Generate a department-grouped payroll report PDF for a given month."""
    from collections import defaultdict
    
    # Fetch all payroll records for this month
    payroll_records = Payroll.query.filter_by(payroll_month=month).all()
    
    if not payroll_records:
        flash(f'No payroll records found for {month}', 'warning')
        return redirect(url_for('payroll.payroll_list'))
    
    # Group by department
    departments = defaultdict(list)
    for record in payroll_records:
        emp = record.employee
        dept = emp.department or 'Unassigned'
        gross = record.basic_salary + record.allowances
        departments[dept].append({
            'name': f"{emp.first_name} {emp.last_name}",
            'emp_no': emp.employment_number,
            'gross': gross,
            'paye': record.payee_tax,
            'loans': record.loan_deduction,
            'absent': record.absentee_deduction,
            'other': record.deductions,
            'net': record.net_salary,
        })
    
    # Format month for display
    try:
        month_date = datetime.strptime(month, '%Y-%m')
        month_display = month_date.strftime('%B %Y')
        month_file = month_date.strftime('%B_%Y')
    except:
        month_display = month
        month_file = month
    
    # Create PDF
    buffer = io.BytesIO()
    doc = create_numbered_doc(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=50)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Company header
    story = add_company_header_to_story(story, layout_mode='normal')
    
    # Report title
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Heading1'],
        fontSize=16, spaceAfter=6, alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    story.append(Paragraph(f"PAYROLL REPORT — {month_display.upper()}", title_style))
    story.append(Spacer(1, 12))
    
    # Grand totals tracking
    grand_total_gross = 0
    grand_total_paye = 0
    grand_total_loans = 0
    grand_total_absent = 0
    grand_total_other = 0
    grand_total_net = 0
    grand_total_employees = 0
    
    page_width = A4[0] - 80  # 40pt margins each side
    
    dept_header_style = ParagraphStyle(
        'DeptHeader', parent=styles['Heading2'],
        fontSize=12, spaceBefore=10, spaceAfter=4,
        textColor=colors.white, backColor=colors.HexColor('#003366'),
        leftIndent=6, leading=18
    )
    
    for dept_name in sorted(departments.keys()):
        employees = departments[dept_name]
        grand_total_employees += len(employees)
        
        # Department header
        story.append(Paragraph(f"DEPARTMENT: {dept_name.upper()}", dept_header_style))
        story.append(Spacer(1, 4))
        
        # Table header
        table_data = [
            ['Name', 'Emp No.', 'Gross Salary', 'PAYE', 'Loans', 'Absent.', 'Other', 'Net Salary']
        ]
        
        dept_gross = 0
        dept_paye = 0
        dept_loans = 0
        dept_absent = 0
        dept_other = 0
        dept_net = 0
        
        for emp in employees:
            table_data.append([
                emp['name'],
                emp['emp_no'],
                f"{emp['gross']:,.2f}",
                f"{emp['paye']:,.2f}",
                f"{emp['loans']:,.2f}",
                f"{emp['absent']:,.2f}",
                f"{emp['other']:,.2f}",
                f"{emp['net']:,.2f}",
            ])
            dept_gross += emp['gross']
            dept_paye += emp['paye']
            dept_loans += emp['loans']
            dept_absent += emp['absent']
            dept_other += emp['other']
            dept_net += emp['net']
        
        # Department subtotal row
        table_data.append([
            f'Subtotal ({len(employees)})', '',
            f"{dept_gross:,.2f}",
            f"{dept_paye:,.2f}",
            f"{dept_loans:,.2f}",
            f"{dept_absent:,.2f}",
            f"{dept_other:,.2f}",
            f"{dept_net:,.2f}",
        ])
        
        grand_total_gross += dept_gross
        grand_total_paye += dept_paye
        grand_total_loans += dept_loans
        grand_total_absent += dept_absent
        grand_total_other += dept_other
        grand_total_net += dept_net
        
        # Column widths: Name(100) EmpNo(55) Gross(70) PAYE(60) Loans(55) Absent(50) Other(50) Net(70) = 510
        col_widths = [100, 55, 70, 60, 55, 50, 50, 70]
        
        dept_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        dept_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Data
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (1, -1), 'LEFT'),
            # Subtotal row
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D6E4F0')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F2F6FA')]),
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        story.append(dept_table)
        story.append(Spacer(1, 10))
    
    # Grand Total section
    story.append(Spacer(1, 6))
    grand_total_style = ParagraphStyle(
        'GrandTotal', parent=styles['Heading2'],
        fontSize=12, spaceBefore=4, spaceAfter=4,
        textColor=colors.darkblue
    )
    story.append(Paragraph("GRAND TOTALS", grand_total_style))
    
    grand_data = [
        ['Total Employees', 'Gross Salary', 'PAYE Tax', 'Loan Ded.', 'Absent. Ded.', 'Other Ded.', 'Net Salary'],
        [
            str(grand_total_employees),
            f"{grand_total_gross:,.2f}",
            f"{grand_total_paye:,.2f}",
            f"{grand_total_loans:,.2f}",
            f"{grand_total_absent:,.2f}",
            f"{grand_total_other:,.2f}",
            f"{grand_total_net:,.2f}",
        ]
    ]
    
    grand_table = Table(grand_data, colWidths=[70, 80, 70, 70, 70, 70, 80])
    grand_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#003366')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#E8EEF5')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(grand_table)
    story.append(Spacer(1, 12))
    
    # Footer note
    story.append(Paragraph("This is a computer-generated payroll report.", styles['Normal']))
    
    # Add signature block and footer
    story = add_signature_block(story, layout_mode='normal')
    story = add_pdf_footer(story, layout_mode='normal')
    
    # Build PDF
    build_pdf_with_numbering(doc, story)
    
    buffer.seek(0)
    secured_buffer = secure_pdf(buffer)
    
    secured_buffer.seek(0)
    response = make_response(secured_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Payroll_Mphamvu_Water_Engineers_{month_file}.pdf'
    
    return response
