from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_file
from models import db, Client, Quotation, QuotationItem, Contract, Invoice, DeliveryNote, Transaction, Notification, CustomProjectType, RFQResponse, RFQResponseCompanyDocument
from datetime import datetime, date, timedelta
from functools import wraps
import re
import io
import json
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from utils.pdf_utils import add_company_header_to_story, add_pdf_footer, add_signature_block, build_pdf_with_numbering, create_numbered_doc, generate_document_number, generate_qr_code, add_signature_stamp_qr, add_stamp_and_qr, generate_document_hash, secure_pdf, add_hash_to_story

from utils.credit_scoring import update_client_credit_score
from utils.auth_utils import apply_dept_filter, get_current_dept
from utils.quotation_location import format_quotation_project_location, parse_optional_coord

quotations_bp = Blueprint('quotations', __name__, url_prefix='/quotations')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['Administrator', 'HR Manager', 'Director', 'Accountant']:
            flash('Administrator or Financial access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@quotations_bp.route('/')
@login_required
def list_quotations():
    query = Quotation.query
    quotations = apply_dept_filter(query, Quotation).order_by(Quotation.created_at.desc()).all()
    return render_template('quotations/list.html', quotations=quotations, timedelta=timedelta)

@quotations_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_quotation():
    rfq_id = request.args.get('rfq_id')
    rfq = None
    if rfq_id:
        from models import RFQRequest
        rfq = RFQRequest.query.get(rfq_id)

    if request.method == 'POST':
        try:
            # Get or create client
            client_name = request.form['client_name']
            client_phone = request.form.get('client_phone')  # Optional
            client_email = request.form.get('client_email')  # Optional
            client_address = request.form['client_address']
            project_types = request.form.getlist('project_type')  # Get all selected project types
            project_type = ', '.join(project_types)  # For client record

            # Check if client exists (first by phone, then by exact name match)
            client = None
            if client_phone:
                client = Client.query.filter_by(phone=client_phone).first()

            if not client:
                # Fallback to name search to prevent duplicates if phone was missed
                # Case-insensitive name match
                client = Client.query.filter(Client.client_name.ilike(client_name.strip())).first()

                # If found by name but missing phone, update phone
                if client and not client.phone and client_phone:
                    client.phone = client_phone
                    db.session.commit()

            if not client:
                client = Client(
                    client_name=client_name,
                    phone=client_phone or None,
                    email=client_email or None,
                    address=client_address,
                    project_type=project_type,
                    department=get_current_dept()
                )
                db.session.add(client)
                db.session.flush()  # Get client_id without committing

            # Create quotation
            project_location = request.form['project_location']
            proj_lat = parse_optional_coord(request.form, 'project_latitude')
            proj_lng = parse_optional_coord(request.form, 'project_longitude')
            borehole_depth = float(request.form.get('borehole_depth', 0)) if request.form.get('borehole_depth') and request.form.get('borehole_depth').strip() else None
            validity_days = int(request.form.get('validity_days', 30) or '30')

            quotation = Quotation(
                client_id=client.client_id,
                project_location=project_location,
                project_latitude=proj_lat,
                project_longitude=proj_lng,
                borehole_depth=borehole_depth,
                total_amount=0,  # Will be calculated below
                validity_days=validity_days,
                description=request.form.get('description', 'We have pleasure in quoting our prices for borehole development as follows;'),
                footnote=request.form.get('footnote') or None,
                status='Pending',
                department=get_current_dept()
            )

            db.session.add(quotation)
            db.session.flush()  # Get quotation_id without committing

            # Create quotation items for each selected project type
            total_amount = 0
            for i, p_type in enumerate(project_types):
                unit = request.form.get(f'project_unit_{i}', '')
                quantity = float(request.form.get(f'project_quantity_{i}', 0) or '0')
                unit_rate = float(request.form.get(f'project_unit_rate_{i}', 0) or '0')

                # Calculate item total
                item_total = quantity * unit_rate
                total_amount += item_total

                # Create quotation item
                quotation_item = QuotationItem(
                    quotation_id=quotation.quotation_id,
                    project_type=p_type,
                    unit=unit,
                    quantity=quantity,
                    unit_rate=unit_rate,
                    total=item_total
                )
                db.session.add(quotation_item)

            # Update quotation total
            quotation.total_amount = total_amount

            # Mark RFQ as processed if present
            if rfq is not None:
                rfq.status = 'processed'  # type: ignore

            db.session.commit()

            # Update client quotation amount
            client.quotation_amount = total_amount
            db.session.commit()

            # Recalculate credit score after quotation creation
            update_client_credit_score(client.client_id)

            flash(f'Quotation created for {client.client_name}', 'success')
            return redirect(url_for('quotations.list_quotations'))

        except Exception as e:
            flash(f'Error creating quotation: {str(e)}', 'error')
            return redirect(url_for('quotations.create_quotation', rfq_id=rfq_id))

    department = request.args.get('department') or session.get('department_context', 'Borehole')
    custom_project_types = CustomProjectType.query.filter_by(department=department).all()
    return render_template('quotations/create.html', rfq=rfq, custom_project_types=[t.project_type for t in custom_project_types], department=department)

@quotations_bp.route('/view/<int:quotation_id>')
@login_required
def view_quotation(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)
    return render_template('quotations/view.html', quotation=quotation, timedelta=timedelta)

@quotations_bp.route('/edit/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_quotation(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)

    if request.method == 'POST':
        try:
            # Update client info
            client = quotation.client
            client.client_name = request.form['client_name']
            client.phone = request.form.get('client_phone') or None
            client.email = request.form.get('client_email') or None
            client.address = request.form['client_address']

            project_types = request.form.getlist('project_type')
            client.project_type = ', '.join(project_types)

            # Update quotation fields
            quotation.project_location = request.form['project_location']
            quotation.project_latitude = parse_optional_coord(request.form, 'project_latitude')
            quotation.project_longitude = parse_optional_coord(request.form, 'project_longitude')
            quotation.description = request.form.get('description', 'We have pleasure in quoting our prices for borehole development as follows;')
            quotation.footnote = request.form.get('footnote') or None

            # Delete existing quotation items
            QuotationItem.query.filter_by(quotation_id=quotation_id).delete()

            # Create new quotation items
            total_amount = 0
            for i, p_type in enumerate(project_types):
                unit = request.form.get(f'project_unit_{i}', '')
                quantity = float(request.form.get(f'project_quantity_{i}', 0) or '0')
                unit_rate = float(request.form.get(f'project_unit_rate_{i}', 0) or '0')

                item_total = quantity * unit_rate
                total_amount += item_total

                quotation_item = QuotationItem(
                    quotation_id=quotation.quotation_id,
                    project_type=p_type,
                    unit=unit,
                    quantity=quantity,
                    unit_rate=unit_rate,
                    total=item_total
                )
                db.session.add(quotation_item)

            # Update quotation total
            quotation.total_amount = total_amount
            client.quotation_amount = total_amount

            db.session.commit()

            # Recalculate credit score after quotation update
            update_client_credit_score(client.client_id)

            flash(f'Quotation updated for {client.client_name}', 'success')
            return redirect(url_for('quotations.list_quotations'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating quotation: {str(e)}', 'error')
            return redirect(url_for('quotations.edit_quotation', quotation_id=quotation_id))

    custom_project_types = CustomProjectType.query.all()
    return render_template('quotations/edit.html', quotation=quotation, custom_project_types=[t.project_type for t in custom_project_types])

@quotations_bp.route('/api/custom_project_types', methods=['POST'])
@login_required
@admin_required
def add_custom_project_type():
    try:
        data = request.get_json()
        project_type = data.get('project_type')
        department = data.get('department', 'Borehole')

        if not project_type:
            return jsonify({'success': False, 'message': 'Project type is required'}), 400

        # Check if already exists in this department
        existing = CustomProjectType.query.filter_by(project_type=project_type, department=department).first()
        if existing:
            return jsonify({'success': False, 'message': 'Project type already exists in this department'}), 400

        new_type = CustomProjectType(project_type=project_type, department=department)
        db.session.add(new_type)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Custom project type added successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@quotations_bp.route('/pdf/<int:quotation_id>')
@login_required
def download_quotation_pdf(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)
    client = quotation.client

    # Handle quotations without items (e.g., ICT, simple borehole quotations)
    quotation_items = quotation.quotation_items if quotation.quotation_items else []
    item_count = len(quotation_items)
    if item_count <= 6:
        layout_mode = "normal"
    elif item_count <= 14:
        layout_mode = "compact"
    else:
        layout_mode = "dense"

    top_margin = 25 if layout_mode == 'normal' else (20 if layout_mode == 'compact' else 15)
    bottom_margin = 30 if layout_mode == 'normal' else (25 if layout_mode == 'compact' else 20)

    # Updated to accommodate 520pt table (595pt A4 width - 520pt = 75pt / 2 = 37.5pt margins)
    left_right_margin = 37.5

    # Create PDF
    buffer = io.BytesIO()
    doc = create_numbered_doc(
        buffer, pagesize=A4,
        rightMargin=left_right_margin, leftMargin=left_right_margin,
        topMargin=top_margin, bottomMargin=bottom_margin
    )
    story = []
    page_width = A4[0] - (left_right_margin * 2)

    # Generate official quotation number
    qtn_number = generate_document_number('QTN', quotation.quotation_id, quotation.created_at)

    # Generate document hash
    doc_hash = generate_document_hash(qtn_number, client.client_name, quotation.total_amount)

    # Generate QR code
    qr_path = generate_qr_code('Quotation', qtn_number, client.client_name, quotation.total_amount)

    # Styles
    styles = getSampleStyleSheet()

    normal_style = ParagraphStyle(
        'NormalCustom', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica', leading=14
    )
    bold_style = ParagraphStyle(
        'BoldCustom', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold', leading=14
    )
    small_style = ParagraphStyle(
        'SmallCustom', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica', leading=13
    )
    italic_style = ParagraphStyle(
        'ItalicCustom', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Oblique', leading=14
    )

    # ── 1. Company Header Image ──
    story = add_company_header_to_story(story, layout_mode=layout_mode, department=quotation.department)

    # ── Horizontal separator line ──
    line_data = [['', '']]
    line_table = Table(line_data, colWidths=[page_width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#003366')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 3))

    # ── 2. Client Info + Date (side by side) ──
    client_address_lines = client.address.replace('\n', '<br/>') if client.address else ''
    client_para = Paragraph(
        f"<b>Client:</b><br/>{client.client_name}<br/>{client_address_lines}",
        normal_style
    )
    date_para = Paragraph(
        f"<b>Quotation No:</b> {qtn_number}<br/><b>Date:</b> {quotation.created_at.strftime('%d/%m/%Y')}",
        normal_style
    )

    info_table = Table(
        [[client_para, date_para]],
        colWidths=[page_width * 0.65, page_width * 0.35]
    )
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)

    # Location row (includes GPS coordinates when stored on the quotation)
    loc_display = format_quotation_project_location(quotation)
    location_table = Table(
        [[Paragraph(f"<b>Location</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{loc_display}", normal_style)]],
        colWidths=[page_width]
    )
    location_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.grey),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(location_table)
    story.append(Spacer(1, 3))

    # ── 3. Greeting & Intro ──
    story.append(Paragraph("Dear Sir/Madam,", italic_style))
    story.append(Spacer(1, 1))

    description_text = quotation.description if quotation.description else "We have pleasure in quoting our prices for borehole development as follows;"
    story.append(Paragraph(description_text, normal_style))
    story.append(Spacer(1, 3))

    # Header row (6 columns restored)
    items_data = [
        [
            Paragraph('<b>ITEM</b>', ParagraphStyle('th', parent=bold_style, fontSize=11)),
            Paragraph('<b>DESCRIPTION</b>', ParagraphStyle('th', parent=bold_style, fontSize=11)),
            Paragraph('<b>UNIT</b>', ParagraphStyle('th', parent=bold_style, fontSize=11)),
            Paragraph('<b>QTY</b>', ParagraphStyle('th', parent=bold_style, fontSize=11)),
            Paragraph('<b>UNIT RATE</b>', ParagraphStyle('th', parent=bold_style, fontSize=11)),
            Paragraph('<b>TOTAL (MK)</b>', ParagraphStyle('th', parent=bold_style, fontSize=11)),
        ]
    ]

    # Data rows from quotation_items
    grand_total = 0
    for idx, item in enumerate(quotation_items, start=1):
        grand_total += item.total

        items_data.append([
            str(idx),
            Paragraph(item.project_type, normal_style),
            item.unit or '',
            f"{int(item.quantity) if item.quantity == int(item.quantity) else item.quantity}",
            f"{item.unit_rate:,.2f}",
            f"{item.total:,.2f}",
        ])

    # If no items, add a single row with the total amount
    if not quotation_items:
        grand_total = quotation.total_amount
        items_data.append([
            '1',
            Paragraph('Project Services', normal_style),
            'Lump Sum',
            '1',
            f"{quotation.total_amount:,.2f}",
            f"{quotation.total_amount:,.2f}",
        ])

    # Grand Total row (inside the table - adjusted for 6 columns)
    items_data.append([
        '', '', '', '',
        Paragraph('<b>Grand Total</b>', ParagraphStyle('gt', parent=bold_style, fontSize=11, alignment=TA_RIGHT)),
        Paragraph(f'<b>{grand_total:,.2f}</b>', ParagraphStyle('gt', parent=bold_style, fontSize=11)),
    ])

    # Fixed Column Widths for 6 columns: [30, 210, 50, 40, 95, 95] = 520 Total
    col_widths = [30, 210, 50, 40, 95, 95]

    col_padding = 4 if layout_mode == 'normal' else (3 if layout_mode == 'compact' else 2)
    font_size = 11 if layout_mode == 'normal' else (10.5 if layout_mode == 'compact' else 10)

    items_table = Table(items_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), font_size),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), font_size),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),   # ITEM col center
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),      # DESCRIPTION left
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),     # UNIT center
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),     # QTY center
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),      # UNIT RATE right
        ('ALIGN', (5, 1), (5, -1), 'RIGHT'),      # TOTAL right
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),      # Align content to top
        ('WORDWRAP', (1, 1), (1, -1), 'CJK'),    # Enable wrapping

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#003366')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f5fa')]),

        # Grand total row
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8eef5')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#003366')),

        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))

    story.append(items_table)
    story.append(Spacer(1, 4))

    # ── 5. Validity & Signature ──
    story.append(Paragraph(
        f"<i>This quotation is valid for {quotation.validity_days} days</i>",
        normal_style
    ))
    story.append(Spacer(1, 1))

    # Add optional footnote if provided
    if quotation.footnote:
        story.append(Spacer(1, 2))
        footnote_text = quotation.footnote.replace('\n', '<br/>')
        story.append(Paragraph(f"<b>Footnote:</b><br/>{footnote_text}", small_style))
        story.append(Spacer(1, 2))

    # Add combined signature, stamp, and QR code block with updated signer details
    story = add_signature_stamp_qr(story, qtn_number, qr_path, layout_mode=layout_mode, signer_name="Ulanda Duwe", signer_title="Managing Director")

    # Add verification hash
    story = add_hash_to_story(story, doc_hash)
    story.append(Spacer(1, 4))

    # ── 6. Bank Details Footer (bordered box) ──
    bank_data = [
        [
            Paragraph('<b>Account Name:</b><br/>Mphamvu Water Engineers', small_style),
            Paragraph('<b>National Bank:</b> 1006978898<br/><b>Standard Bank:</b> 9100005388640', small_style),
            Paragraph('<b>Branch:</b> Capital City', small_style),
        ]
    ]

    bank_table = Table(bank_data, colWidths=[page_width * 0.35, page_width * 0.40, page_width * 0.25])
    bank_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#003366')),
        ('LINEAFTER', (0, 0), (0, 0), 0.5, colors.HexColor('#003366')),
        ('LINEAFTER', (1, 0), (1, 0), 0.5, colors.HexColor('#003366')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f8fc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    story.append(bank_table)

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
    safe_client = re.sub(r'[^A-Za-z0-9_]', '_', client.client_name)
    response.headers['Content-Disposition'] = f'attachment; filename=Quotation_{safe_client}.pdf'

    return response

@quotations_bp.route('/approve/<int:quotation_id>', methods=['POST'])
@login_required
@admin_required
def approve_quotation(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)

    try:
        # Create contract
        contract = Contract(
            quotation_id=quotation_id,
            contract_date=date.today(),
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date(),
            status='Approved',
            notes=request.form.get('notes'),
            department=quotation.department
        )

        db.session.add(contract)

        # Update quotation status
        quotation.status = 'Approved'

        # Update client status
        quotation.client.contract_status = 'Approved'

        db.session.commit()

        # Recalculate credit score after new invoice creation (affects outstanding balance ratio)
        update_client_credit_score(quotation.client_id)

        flash(f'Quotation approved successfully. Project is now active.', 'success')
        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('quotations.list_quotations'))

    except Exception as e:
        flash(f'Error approving quotation: {str(e)}', 'error')
        return redirect(url_for('quotations.view_quotation', quotation_id=quotation_id))

@quotations_bp.route('/delete/<int:quotation_id>', methods=['POST'])
@login_required
@admin_required
def delete_quotation(quotation_id):
    try:
        quotation = Quotation.query.get_or_404(quotation_id)
        client_id_to_update = quotation.client_id

        # Cascade delete using direct quotation_id relationships

        # First delete delivery notes linked directly
        DeliveryNote.query.filter_by(quotation_id=quotation_id).delete()

        # Find invoices linked to this quotation to clear transactions
        invoices = Invoice.query.filter_by(quotation_id=quotation_id).all()
        for invoice in invoices:
            DeliveryNote.query.filter_by(invoice_id=invoice.invoice_id).delete() # Catch any old ones
            Transaction.query.filter_by(invoice_id=invoice.invoice_id).delete()

        Invoice.query.filter_by(quotation_id=quotation_id).delete()

        # Also clean up old logic items just in case
        for contract in quotation.contracts:
            for invoice in contract.invoices:
                DeliveryNote.query.filter_by(invoice_id=invoice.invoice_id).delete()
                Transaction.query.filter_by(invoice_id=invoice.invoice_id).delete()
            Invoice.query.filter_by(contract_id=contract.contract_id).delete()

        # Delete contracts
        Contract.query.filter_by(quotation_id=quotation_id).delete()

        # Delete quotation items
        QuotationItem.query.filter_by(quotation_id=quotation_id).delete()

        # Delete the quotation
        db.session.delete(quotation)
        db.session.commit()

        # Recalculate credit score after quotation delete
        update_client_credit_score(client_id_to_update)

        return jsonify({'success': True, 'message': 'Quotation and all related records deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@quotations_bp.route('/generate_rfq_response', methods=['POST'])
@login_required
def generate_rfq_response():
    """Generate a dynamic RFQ Response PDF from the form data and save to database."""
    import json
    import os
    import tempfile
    from werkzeug.utils import secure_filename

    try:
        # Parse table data from JSON string
        table_data_raw = request.form.get('table_data', '{}')
        table_data = json.loads(table_data_raw)

        # Validate that table data has actual content
        rows = table_data.get('rows', [])
        if not rows:
            return jsonify({'error': 'No items found in the RFQ table. Please add at least one item before generating the PDF.'}), 400

        # Collect all form fields
        form_data = {
            'company': request.form.get('company', ''),
            'contact': request.form.get('contact', ''),
            'phone': request.form.get('phone', ''),
            'email': request.form.get('email', ''),
            'reg_no': request.form.get('reg_no', ''),
            'water_reg_no': request.form.get('water_reg_no', ''),
            'location': request.form.get('location', ''),
            'work_required': request.form.get('work_required', ''),
            'yield_value': request.form.get('yield_value', ''),
            'warranty_borehole': request.form.get('warranty_borehole', ''),
            'warranty_pump': request.form.get('warranty_pump', ''),
            'days_to_complete': request.form.get('days_to_complete', ''),
            'deposit': request.form.get('deposit', ''),
            'balance_condition': request.form.get('balance_condition', ''),
            'validity_days': request.form.get('validity_days', ''),
            'table_data': table_data,
        }

        # Resolve the current department from session
        current_dept = get_current_dept()

        # Save or update RFQ response in database
        rfq_response_id = request.form.get('rfq_response_id')
        if rfq_response_id:
            # Load existing RFQ response and update all fields from the live form
            rfq_response = RFQResponse.query.get(int(rfq_response_id))

            # Enforce ownership: must be the creating user
            if not rfq_response or rfq_response.created_by != session.get('user_id'):
                return jsonify({'error': 'Invalid RFQ response ID or permission denied'}), 403

            # Enforce department isolation: cannot edit an RFQ from another department
            if rfq_response.department != current_dept:
                return jsonify({'error': 'Access denied: this RFQ belongs to a different department'}), 403

            rfq_response.company = form_data['company']
            rfq_response.contact = form_data['contact']
            rfq_response.phone = form_data['phone']
            rfq_response.email = form_data['email']
            rfq_response.reg_no = form_data['reg_no']
            rfq_response.water_reg_no = form_data['water_reg_no']
            rfq_response.location = form_data['location']
            rfq_response.work_required = form_data['work_required']
            rfq_response.yield_value = form_data['yield_value']
            rfq_response.warranty_borehole = form_data['warranty_borehole']
            rfq_response.warranty_pump = form_data['warranty_pump']
            rfq_response.days_to_complete = form_data['days_to_complete']
            rfq_response.deposit = form_data['deposit']
            rfq_response.balance_condition = form_data['balance_condition']
            rfq_response.validity_days = form_data['validity_days']
            rfq_response.table_data = json.dumps(table_data)

            db.session.commit()
        else:
            # Generate a unique RFQ code
            import uuid
            import random
            from datetime import datetime
            
            # Format: MPH-RFQ-{Year}{Month}-{Random 4 chars}
            # e.g., MPH-RFQ-2605-A1B2
            year_month = datetime.utcnow().strftime('%y%m')
            random_str = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
            rfq_code = f"MPH-RFQ-{year_month}-{random_str}"
            
            # Create new RFQ response — tag it with the current department
            rfq_response = RFQResponse(
                reference_number=rfq_code,
                company=form_data['company'],
                contact=form_data['contact'],
                phone=form_data['phone'],
                email=form_data['email'],
                reg_no=form_data['reg_no'],
                water_reg_no=form_data['water_reg_no'],
                location=form_data['location'],
                work_required=form_data['work_required'],
                yield_value=form_data['yield_value'],
                warranty_borehole=form_data['warranty_borehole'],
                warranty_pump=form_data['warranty_pump'],
                days_to_complete=form_data['days_to_complete'],
                deposit=form_data['deposit'],
                balance_condition=form_data['balance_condition'],
                validity_days=form_data['validity_days'],
                table_data=json.dumps(table_data),
                created_by=session.get('user_id'),
                department=current_dept
            )
            db.session.add(rfq_response)
            db.session.commit()

        # Handle uploaded company documents (multi-file) + removals
        removed_ids_raw = request.form.get('removed_company_document_ids', '').strip()
        removed_ids = []
        if removed_ids_raw:
            for part in removed_ids_raw.split(','):
                part = part.strip()
                if part.isdigit():
                    removed_ids.append(int(part))

        if removed_ids:
            docs_to_delete = RFQResponseCompanyDocument.query.filter(
                RFQResponseCompanyDocument.id.in_(removed_ids),
                RFQResponseCompanyDocument.rfq_response_id == rfq_response.id,
            ).all()

            for doc in docs_to_delete:
                try:
                    if doc.storage_path and os.path.exists(doc.storage_path):
                        os.remove(doc.storage_path)
                except Exception:
                    pass
                db.session.delete(doc)

        uploaded_files = request.files.getlist('company_documents')
        if uploaded_files:
            import uuid

            allowed_ext = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg'}
            upload_base_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'uploads',
                'rfq_company_documents',
                str(rfq_response.id),
            )
            os.makedirs(upload_base_dir, exist_ok=True)

            for f in uploaded_files:
                if not f or not f.filename:
                    continue

                original_name = f.filename
                filename = secure_filename(original_name)
                ext = os.path.splitext(filename)[1].lower()
                if ext not in allowed_ext:
                    continue

                unique_name = f"{uuid.uuid4().hex}_{filename}"
                storage_path = os.path.join(upload_base_dir, unique_name)
                f.save(storage_path)

                doc = RFQResponseCompanyDocument(
                    rfq_response_id=rfq_response.id,
                    filename=original_name,
                    storage_path=storage_path,
                    mime_type=getattr(f, 'mimetype', None),
                )
                db.session.add(doc)

        db.session.commit()

        # Use the current form data (table_data and fields) as the direct source of truth.
        # This guarantees that the generated PDF always reflects exactly what the user sees and entered on screen.
        pdf_form_data = {
            'reference_number': getattr(rfq_response, 'reference_number', ''),
            'company': form_data['company'],
            'contact': form_data['contact'],
            'phone': form_data['phone'],
            'email': form_data['email'],
            'reg_no': form_data['reg_no'],
            'water_reg_no': form_data['water_reg_no'],
            'location': form_data['location'],
            'work_required': form_data['work_required'],
            'yield_value': form_data['yield_value'],
            'warranty_borehole': form_data['warranty_borehole'],
            'warranty_pump': form_data['warranty_pump'],
            'days_to_complete': form_data['days_to_complete'],
            'deposit': form_data['deposit'],
            'balance_condition': form_data['balance_condition'],
            'validity_days': form_data['validity_days'],
            'department': request.form.get('department', '') or session.get('department_context', 'Borehole'),
            'table_data': table_data,
        }

        company_document_paths = [
            d.storage_path
            for d in RFQResponseCompanyDocument.query.filter_by(
                rfq_response_id=rfq_response.id
            ).all()
        ]

        from utils.pdf_utils import generate_dynamic_rfq_pdf
        pdf_buffer = generate_dynamic_rfq_pdf(
            pdf_form_data,
            company_document_paths=company_document_paths,
        )

        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=RFQ_Response_{rfq_response.id}.pdf'
        response.headers['X-RFQ-Response-ID'] = str(rfq_response.id)
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@quotations_bp.route('/load_rfq_response/<int:rfq_response_id>', methods=['GET'])
@login_required
def load_rfq_response(rfq_response_id):
    """Load a saved RFQ response for editing."""
    try:
        rfq_response = RFQResponse.query.get_or_404(rfq_response_id)
        user_role = session.get('role', '')
        is_director = user_role in ['Managing Director', 'Director']

        # Enforce ownership: must be the creating user (Directors are exempt)
        if not is_director and rfq_response.created_by != session.get('user_id'):
            return jsonify({'error': 'You do not have permission to access this RFQ response'}), 403

        # Enforce department isolation (Directors can cross departments)
        if not is_director and rfq_response.department != get_current_dept():
            return jsonify({'error': 'Access denied: this RFQ belongs to a different department'}), 403

        # Return the RFQ response data
        return jsonify({
            'success': True,
            'data': {
                'id': rfq_response.id,
                'company': rfq_response.company,
                'contact': rfq_response.contact,
                'phone': rfq_response.phone,
                'email': rfq_response.email,
                'reg_no': rfq_response.reg_no,
                'water_reg_no': rfq_response.water_reg_no,
                'location': rfq_response.location,
                'work_required': rfq_response.work_required,
                'yield_value': rfq_response.yield_value,
                'warranty_borehole': rfq_response.warranty_borehole,
                'warranty_pump': rfq_response.warranty_pump,
                'days_to_complete': rfq_response.days_to_complete,
                'deposit': rfq_response.deposit,
                'balance_condition': rfq_response.balance_condition,
                'validity_days': rfq_response.validity_days,
                'table_data': json.loads(rfq_response.table_data) if rfq_response.table_data else {},
                'created_at': rfq_response.created_at.strftime('%Y-%m-%d %H:%M:%S') if rfq_response.created_at else None,
                'updated_at': rfq_response.updated_at.strftime('%Y-%m-%d %H:%M:%S') if rfq_response.updated_at else None,
                'department': rfq_response.department,
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@quotations_bp.route('/rfq_company_documents/<int:rfq_response_id>', methods=['GET'])
@login_required
def list_rfq_company_documents(rfq_response_id):
    """Return company-document attachments for a saved RFQ response."""
    try:
        rfq_response = RFQResponse.query.get_or_404(rfq_response_id)
        user_role = session.get('role', '')
        is_director = user_role in ['Managing Director', 'Director']

        if not is_director and rfq_response.created_by != session.get('user_id'):
            return jsonify({'error': 'You do not have permission to access this RFQ response'}), 403

        if not is_director and rfq_response.department != get_current_dept():
            return jsonify({'error': 'Access denied: this RFQ belongs to a different department'}), 403

        docs = (
            RFQResponseCompanyDocument.query.filter_by(rfq_response_id=rfq_response.id)
            .order_by(RFQResponseCompanyDocument.uploaded_at.desc())
            .all()
        )

        return jsonify({
            'success': True,
            'data': [
                {
                    'id': d.id,
                    'filename': d.filename,
                    'mime_type': d.mime_type,
                }
                for d in docs
            ],
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@quotations_bp.route('/preview_rfq_company_document/<int:doc_id>', methods=['GET'])
@login_required
def preview_rfq_company_document(doc_id):
    """Serve an uploaded company document for in-browser preview."""
    try:
        doc = RFQResponseCompanyDocument.query.get_or_404(doc_id)
        rfq_response = doc.rfq_response

        user_role = session.get('role', '')
        is_director = user_role in ['Managing Director', 'Director']

        if not is_director and rfq_response.created_by != session.get('user_id'):
            return jsonify({'error': 'You do not have permission to access this RFQ document'}), 403

        if not is_director and rfq_response.department != get_current_dept():
            return jsonify({'error': 'Access denied: this RFQ belongs to a different department'}), 403

        return send_file(
            doc.storage_path,
            mimetype=doc.mime_type or None,
            as_attachment=False,
            download_name=doc.filename,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@quotations_bp.route('/download_rfq_company_document/<int:doc_id>', methods=['GET'])
@login_required
def download_rfq_company_document(doc_id):
    """Serve an uploaded company document as a download."""
    try:
        doc = RFQResponseCompanyDocument.query.get_or_404(doc_id)
        rfq_response = doc.rfq_response

        user_role = session.get('role', '')
        is_director = user_role in ['Managing Director', 'Director']

        if not is_director and rfq_response.created_by != session.get('user_id'):
            return jsonify({'error': 'You do not have permission to access this RFQ document'}), 403

        if not is_director and rfq_response.department != get_current_dept():
            return jsonify({'error': 'Access denied: this RFQ belongs to a different department'}), 403

        return send_file(
            doc.storage_path,
            mimetype=doc.mime_type or None,
            as_attachment=True,
            download_name=doc.filename,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@quotations_bp.route('/rfq_responses', methods=['GET'])
@login_required
def list_rfq_responses():
    """List saved RFQ responses, scoped to the current department.

    Managing Director / Director roles see all RFQs across departments.
    All other roles see only RFQs they created within their current department.
    """
    try:
        user_role = session.get('role', '')
        is_director = user_role in ['Managing Director', 'Director']

        if is_director:
            # Directors see every RFQ across all departments
            rfq_responses = RFQResponse.query.order_by(RFQResponse.updated_at.desc()).all()
        else:
            # All other users: scoped to their user ID AND current active department
            rfq_responses = RFQResponse.query.filter_by(
                created_by=session.get('user_id'),
                department=get_current_dept()
            ).order_by(RFQResponse.updated_at.desc()).all()

        response_data = []
        for rfq in rfq_responses:
            response_data.append({
                'id': rfq.id,
                'reference_number': getattr(rfq, 'reference_number', '') or '',
                'company': rfq.company,
                'location': rfq.location,
                'department': rfq.department,
                'created_at': rfq.created_at.strftime('%Y-%m-%d %H:%M:%S') if rfq.created_at else None,
                'updated_at': rfq.updated_at.strftime('%Y-%m-%d %H:%M:%S') if rfq.updated_at else None,
            })

        return jsonify({'success': True, 'data': response_data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@quotations_bp.route('/rfq_response_pdf/<int:rfq_response_id>', methods=['GET'])
@login_required
def download_rfq_response_pdf(rfq_response_id):
    """Generate and download the PDF for a previously saved RFQ response."""
    try:
        rfq_response = RFQResponse.query.get_or_404(rfq_response_id)
        user_role = session.get('role', '')
        is_director = user_role in ['Managing Director', 'Director']

        # Enforce ownership: must be the creating user (Directors are exempt)
        if not is_director and rfq_response.created_by != session.get('user_id'):
            return jsonify({'error': 'You do not have permission to access this RFQ response'}), 403

        # Enforce department isolation (Directors can cross departments)
        if not is_director and rfq_response.department != get_current_dept():
            return jsonify({'error': 'Access denied: this RFQ belongs to a different department'}), 403

        import json
        table_data = json.loads(rfq_response.table_data) if rfq_response.table_data else {}

        pdf_form_data = {
            'reference_number': getattr(rfq_response, 'reference_number', '') or '',
            'company': rfq_response.company or '',
            'contact': rfq_response.contact or '',
            'phone': rfq_response.phone or '',
            'email': rfq_response.email or '',
            'reg_no': rfq_response.reg_no or '',
            'water_reg_no': rfq_response.water_reg_no or '',
            'location': rfq_response.location or '',
            'work_required': rfq_response.work_required or '',
            'yield_value': rfq_response.yield_value or '',
            'warranty_borehole': rfq_response.warranty_borehole or '',
            'warranty_pump': rfq_response.warranty_pump or '',
            'days_to_complete': rfq_response.days_to_complete or '',
            'deposit': rfq_response.deposit or '',
            'balance_condition': rfq_response.balance_condition or '',
            'validity_days': rfq_response.validity_days or '',
            'department': rfq_response.department,
            'table_data': table_data,
        }

        company_document_paths = [
            d.storage_path
            for d in RFQResponseCompanyDocument.query.filter_by(
                rfq_response_id=rfq_response.id
            ).all()
        ]

        from utils.pdf_utils import generate_dynamic_rfq_pdf
        pdf_buffer = generate_dynamic_rfq_pdf(
            pdf_form_data,
            company_document_paths=company_document_paths,
        )

        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=RFQ_Response_{rfq_response.id}.pdf'
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@quotations_bp.route('/delete_rfq_response/<int:rfq_response_id>', methods=['POST'])
@login_required
def delete_rfq_response(rfq_response_id):
    """Delete a saved RFQ response."""
    try:
        import os

        rfq_response = RFQResponse.query.get_or_404(rfq_response_id)
        user_role = session.get('role', '')
        is_director = user_role in ['Managing Director', 'Director']

        # Enforce ownership: must be the creating user (Directors are exempt)
        if not is_director and rfq_response.created_by != session.get('user_id'):
            return jsonify({'success': False, 'message': 'You do not have permission to delete this RFQ response'}), 403

        # Enforce department isolation
        if not is_director and rfq_response.department != get_current_dept():
            return jsonify({'success': False, 'message': 'Access denied: this RFQ belongs to a different department'}), 403

        # Delete stored company documents from disk
        docs = RFQResponseCompanyDocument.query.filter_by(rfq_response_id=rfq_response.id).all()
        for doc in docs:
            try:
                if doc.storage_path and os.path.exists(doc.storage_path):
                    os.remove(doc.storage_path)
            except Exception:
                pass

        db.session.delete(rfq_response)
        db.session.commit()

        return jsonify({'success': True, 'message': 'RFQ response deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

