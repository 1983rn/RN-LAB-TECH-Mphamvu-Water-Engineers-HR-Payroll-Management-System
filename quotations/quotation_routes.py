from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from models import db, Client, Quotation, QuotationItem, Contract, Invoice, DeliveryNote, Transaction, Notification
from datetime import datetime, date, timedelta
from functools import wraps
import re
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from utils.pdf_utils import add_company_header_to_story, add_pdf_footer, add_signature_block, build_pdf_with_numbering, create_numbered_doc, generate_document_number, generate_qr_code, add_stamp_and_qr, generate_document_hash, secure_pdf, add_hash_to_story

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
        if session.get('role') not in ['Administrator', 'HR Manager']:
            flash('Administrator access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@quotations_bp.route('/')
@login_required
def list_quotations():
    quotations = Quotation.query.order_by(Quotation.created_at.desc()).all()
    return render_template('quotations/list.html', quotations=quotations, timedelta=timedelta)

@quotations_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_quotation():
    if request.method == 'POST':
        try:
            # Get or create client
            client_name = request.form['client_name']
            client_phone = request.form.get('client_phone')  # Optional
            client_email = request.form.get('client_email')  # Optional
            client_address = request.form['client_address']
            project_types = request.form.getlist('project_type')  # Get all selected project types
            project_type = ', '.join(project_types)  # For client record
            
            # Check if client exists (only if phone is provided)
            client = None
            if client_phone:
                client = Client.query.filter_by(phone=client_phone).first()
            
            if not client:
                client = Client(
                    client_name=client_name,
                    phone=client_phone or None,
                    email=client_email or None,
                    address=client_address,
                    project_type=project_type
                )
                db.session.add(client)
                db.session.flush()  # Get client_id without committing
            
            # Create quotation
            project_location = request.form['project_location']
            borehole_depth = float(request.form.get('borehole_depth', 0)) if request.form.get('borehole_depth') and request.form.get('borehole_depth').strip() else None
            validity_days = int(request.form.get('validity_days', 30) or '30')
            
            quotation = Quotation(
                client_id=client.client_id,
                project_location=project_location,
                borehole_depth=borehole_depth,
                total_amount=0,  # Will be calculated below
                validity_days=validity_days,
                description=request.form.get('description', 'We have pleasure in quoting our prices for borehole development as follows;'),
                status='Pending'
            )
            
            db.session.add(quotation)
            db.session.flush()  # Get quotation_id without committing
            
            # Create quotation items for each selected project type
            total_amount = 0
            for i, project_type in enumerate(project_types):
                unit = request.form.get(f'project_unit_{i}', '')
                quantity = float(request.form.get(f'project_quantity_{i}', 0) or '0')
                unit_rate = float(request.form.get(f'project_unit_rate_{i}', 0) or '0')
                
                # Calculate item total
                item_total = quantity * unit_rate
                total_amount += item_total
                
                # Create quotation item
                quotation_item = QuotationItem(
                    quotation_id=quotation.quotation_id,
                    project_type=project_type,
                    unit=unit,
                    quantity=quantity,
                    unit_rate=unit_rate,
                    total=item_total
                )
                db.session.add(quotation_item)
            
            # Update quotation total
            quotation.total_amount = total_amount
            db.session.commit()
            
            # Update client quotation amount
            client.quotation_amount = total_amount
            db.session.commit()
            
            flash(f'Quotation created for {client.client_name}', 'success')
            return redirect(url_for('quotations.list_quotations'))
            
        except Exception as e:
            flash(f'Error creating quotation: {str(e)}', 'error')
            return redirect(url_for('quotations.create_quotation'))
    
    return render_template('quotations/create.html')

@quotations_bp.route('/view/<int:quotation_id>')
@login_required
def view_quotation(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)
    return render_template('quotations/view.html', quotation=quotation, timedelta=timedelta)

@quotations_bp.route('/pdf/<int:quotation_id>')
@login_required
def download_quotation_pdf(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)
    client = quotation.client
    
    item_count = len(quotation.quotation_items)
    if item_count <= 10:
        layout_mode = "normal"
    elif item_count <= 20:
        layout_mode = "compact"
    else:
        layout_mode = "dense"
        
    top_margin = 35 if layout_mode == 'normal' else (30 if layout_mode == 'compact' else 25)
    bottom_margin = 40 if layout_mode == 'normal' else (35 if layout_mode == 'compact' else 30)
    
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
    story = add_company_header_to_story(story, layout_mode=layout_mode)
    
    # ── Horizontal separator line ──
    line_data = [['', '']]
    line_table = Table(line_data, colWidths=[page_width])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#003366')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 5))
    
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
    
    # Location row
    location_table = Table(
        [[Paragraph(f"<b>Location</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{quotation.project_location}", normal_style)]],
        colWidths=[page_width]
    )
    location_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.grey),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(location_table)
    story.append(Spacer(1, 5))
    
    # ── 3. Greeting & Intro ──
    story.append(Paragraph("Dear Sir/Madam,", italic_style))
    story.append(Spacer(1, 3))
    
    description_text = quotation.description if quotation.description else "We have pleasure in quoting our prices for borehole development as follows;"
    story.append(Paragraph(description_text, normal_style))
    story.append(Spacer(1, 5))
    
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
    for idx, item in enumerate(quotation.quotation_items, start=1):
        grand_total += item.total
        
        items_data.append([
            str(idx),
            Paragraph(item.project_type, normal_style),
            item.unit or '',
            f"{int(item.quantity) if item.quantity == int(item.quantity) else item.quantity}",
            f"{item.unit_rate:,.2f}",
            f"{item.total:,.2f}",
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
    story.append(Spacer(1, 6))
    
    # ── 5. Validity & Signature ──
    story.append(Paragraph(
        f"<i>This quotation is valid for {quotation.validity_days} days</i>",
        normal_style
    ))
    story.append(Spacer(1, 3))
    
    # Add signature block
    story = add_signature_block(story, layout_mode=layout_mode)
    
    # Add stamp and QR code
    story = add_stamp_and_qr(story, qtn_number, qr_path, layout_mode=layout_mode)
    
    # Add verification hash
    story = add_hash_to_story(story, doc_hash)
    story.append(Spacer(1, 8))
    
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
            notes=request.form.get('notes')
        )
        
        db.session.add(contract)
        
        # Update quotation status
        quotation.status = 'Approved'
        
        # Update client status
        quotation.client.contract_status = 'Approved'
        
        db.session.commit()
        
        flash('Quotation approved and contract created!', 'success')
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
        
        return jsonify({'success': True, 'message': 'Quotation and all related records deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
