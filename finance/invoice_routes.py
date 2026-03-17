from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from models import db, Contract, Invoice, DeliveryNote, Transaction, Quotation
from datetime import datetime, date, timedelta
from functools import wraps
import re
import io
import hashlib
from flask import jsonify
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from utils.pdf_utils import add_company_header_to_story, add_pdf_footer, add_signature_block, build_pdf_with_numbering, create_numbered_doc, generate_document_number, generate_qr_code, add_stamp_and_qr, generate_document_hash, secure_pdf, add_hash_to_story

finance_bp = Blueprint('finance', __name__, url_prefix='/finance')

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

@finance_bp.route('/invoices')
@login_required
@admin_required
def list_invoices():
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
    # Fetch approved quotations that haven't been delivered
    approved_quotations = Quotation.query.filter_by(status='Approved', delivery_confirmed=False).all()
    return render_template('finance/invoices/list.html', invoices=invoices, approved_quotations=approved_quotations)

@finance_bp.route('/invoice/generate/<int:contract_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def generate_invoice(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    
    if request.method == 'POST':
        try:
            # Generate invoice number using full precise timestamp and contract ID for guaranteed uniqueness
            invoice_number = f"INV{datetime.now().strftime('%Y%m%d%H%M%S')}{contract.contract_id:04d}"
            
            # Create invoice
            invoice = Invoice(
                contract_id=contract_id,
                invoice_number=invoice_number,
                invoice_date=date.today(),
                due_date=date.today() + timedelta(days=14),
                amount=contract.quotation.total_amount,
                payment_terms=request.form.get('payment_terms', 'Payment within 14 days'),
                status='Unpaid'
            )
            
            db.session.add(invoice)
            
            # Update contract status
            contract.status = 'Invoiced'
            
            db.session.commit()
            
            flash(f'Invoice {invoice_number} generated successfully!', 'success')
            return redirect(url_for('finance.list_invoices'))
            
        except Exception as e:
            flash(f'Error generating invoice: {str(e)}', 'error')
            return redirect(url_for('finance.generate_invoice', contract_id=contract_id))
    
    return render_template('finance/invoices/generate.html', contract=contract)

@finance_bp.route('/invoice/pdf/<int:invoice_id>')
@login_required
def download_invoice_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    contract = invoice.contract
    quotation = contract.quotation
    client = quotation.client
    
    # Force tightest layout to fit on one page
    layout_mode = "dense"
        
    top_margin = 30
    bottom_margin = 30
    
    # 51 points is approx 18mm
    buffer = io.BytesIO()
    doc = create_numbered_doc(buffer, pagesize=A4, rightMargin=51, leftMargin=51, topMargin=top_margin, bottomMargin=bottom_margin)
    story = []
    
    inv_number = generate_document_number('INV', invoice.invoice_id, invoice.created_at)
    doc_hash = generate_document_hash(inv_number, client.client_name, quotation.total_amount)
    qr_path = generate_qr_code('Invoice', inv_number, client.client_name, quotation.total_amount)
    
    story = add_company_header_to_story(story, layout_mode=layout_mode)
    
    col_padding = 2
    font_size = 9
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        leading=14,
        spaceAfter=2,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 2))
    
    invoice_info = [
        ['Invoice Number:', inv_number],
        ['Invoice Date:', invoice.invoice_date.strftime('%d/%m/%Y')],
        ['Due Date:', invoice.due_date.strftime('%d/%m/%Y')],
    ]
    
    invoice_table = Table(invoice_info, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
    ]))
    
    story.append(invoice_table)
    story.append(Spacer(1, 2))
    
    # Client Details
    story.append(Paragraph("BILL TO:", ParagraphStyle('BillTo', parent=styles['Heading3'], fontSize=10, leading=10, spaceAfter=2)))
    client_data = [
        [client.client_name],
        [Paragraph(client.address.replace('\n', '<br/>'), ParagraphStyle('ClientAddr', parent=styles['Normal'], fontSize=9, leading=10)) if client.address else ''],
        [client.phone],
        [client.email] if client.email else [''],
    ]
    
    client_table = Table(client_data, colWidths=[5*inch])
    client_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
    ]))
    
    story.append(client_table)
    story.append(Spacer(1, 2))
    
    # Project Description
    story.append(Paragraph("PROJECT DETAILS", ParagraphStyle('ProjDetails', parent=styles['Heading3'], fontSize=10, leading=10, spaceAfter=2)))
    story.append(Paragraph(f"Project: {client.project_type}", ParagraphStyle('ProjText', parent=styles['Normal'], fontSize=9, leading=10)))
    story.append(Paragraph(f"Location: {quotation.project_location}", ParagraphStyle('LocText', parent=styles['Normal'], fontSize=9, leading=10)))
    story.append(Spacer(1, 2))
    
    # Invoice Items
    story.append(Paragraph("INVOICE ITEMS", ParagraphStyle('InvItems', parent=styles['Heading3'], fontSize=10, leading=10, spaceAfter=2)))
    items_data = [
        ['Description', 'Quantity', 'Unit Price', 'Total']
    ]
    
    for item in quotation.quotation_items:
        qty_str = f"{int(item.quantity) if item.quantity == int(item.quantity) else item.quantity}"
        if item.unit:
            qty_str += f" {item.unit}"
        items_data.append([
            item.project_type, 
            qty_str, 
            f"{item.unit_rate:,.2f}", 
            f"{item.total:,.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch], repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 2))
    
    # Summary
    summary_data = [
        ['Subtotal:', f"{quotation.total_amount:,.2f}"],
        ['VAT (0%):', '0.00'],
        ['Total Amount:', f"{quotation.total_amount:,.2f}"],
        ['Paid Amount:', f"{invoice.paid_amount:,.2f}"],
        ['Balance Due:', f"{invoice.amount - invoice.paid_amount:,.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[4*inch, 1*inch])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
        ('FONTNAME', (0, 4), (-1, 4), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 4), (-1, 4), colors.red),
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 2))
    
    # Payment Terms
    story.append(Paragraph("PAYMENT TERMS", ParagraphStyle('PaymentTermsHeader', parent=styles['Heading3'], fontSize=10, leading=10, spaceAfter=2)))
    story.append(Paragraph(invoice.payment_terms, ParagraphStyle('PaymentTerms', parent=styles['Normal'], fontSize=9, leading=10)))
    story.append(Spacer(1, 2))
    
    # Bank Details
    story.append(Paragraph("BANK DETAILS", ParagraphStyle('BankDetails', parent=styles['Heading3'], fontSize=10, leading=10, spaceAfter=2)))
    bank_data = [
        ['Account Name:', 'Mphamvu Water Engineers'],
        ['National Bank:', '1006978898'],
        ['Standard Bank:', '9100005388640'],
        ['Branch:', 'Capital City'],
    ]
    
    bank_table = Table(bank_data, colWidths=[2*inch, 3*inch])
    bank_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
    ]))
    
    story.append(bank_table)
    story.append(Spacer(1, 5))
    
    story = add_signature_block(story, layout_mode=layout_mode)
    story = add_stamp_and_qr(story, inv_number, qr_path)
    story = add_hash_to_story(story, doc_hash)
    story = add_pdf_footer(story, layout_mode=layout_mode)
    build_pdf_with_numbering(doc, story)
    
    buffer.seek(0)
    secured_buffer = secure_pdf(buffer)
    
    secured_buffer.seek(0)
    response = make_response(secured_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    safe_client = re.sub(r'[^A-Za-z0-9_]', '_', client.client_name)
    response.headers['Content-Disposition'] = f'attachment; filename=Invoice_{safe_client}.pdf'
    
    return response

@finance_bp.route('/delivery-notes')
@login_required
@admin_required
def list_delivery_notes():
    delivery_notes = DeliveryNote.query.order_by(DeliveryNote.created_at.desc()).all()
    # Fetch approved quotations that haven't been delivered
    approved_quotations = Quotation.query.filter_by(status='Approved', delivery_confirmed=False).all()
    return render_template('finance/delivery/list.html', delivery_notes=delivery_notes, approved_quotations=approved_quotations)

@finance_bp.route('/delivery-note/create/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def create_delivery_note(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if request.method == 'POST':
        try:
            delivery_note = DeliveryNote(
                invoice_id=invoice_id,
                delivery_date=datetime.strptime(request.form['delivery_date'], '%Y-%m-%d').date(),
                equipment_delivered=request.form['equipment_delivered'],
                delivered_by=request.form['delivered_by'],
                received_by=request.form.get('received_by'),
                notes=request.form.get('notes')
            )
            
            db.session.add(delivery_note)
            
            # Update invoice status
            invoice.status = 'Delivered'
            
            db.session.commit()
            
            flash('Delivery note created successfully!', 'success')
            return redirect(url_for('finance.list_delivery_notes'))
            
        except Exception as e:
            flash(f'Error creating delivery note: {str(e)}', 'error')
            return redirect(url_for('finance.create_delivery_note', invoice_id=invoice_id))
    
    return render_template('finance/delivery/create.html', invoice=invoice)

@finance_bp.route('/delivery-note/pdf/<int:delivery_id>')
@login_required
def download_delivery_note_pdf(delivery_id):
    delivery_note = DeliveryNote.query.get_or_404(delivery_id)
    invoice = delivery_note.invoice
    contract = invoice.contract
    quotation = contract.quotation
    client = quotation.client
    
    # Force tightest layout to fit on one page
    layout_mode = "dense"
        
    top_margin = 30
    bottom_margin = 30
    
    buffer = io.BytesIO()
    doc = create_numbered_doc(buffer, pagesize=A4, rightMargin=51, leftMargin=51, topMargin=top_margin, bottomMargin=bottom_margin)
    story = []
    
    dn_number = generate_document_number('DN', delivery_note.delivery_id, delivery_note.created_at)
    inv_number = generate_document_number('INV', invoice.invoice_id, invoice.created_at)
    doc_hash = generate_document_hash(dn_number, client.client_name)
    qr_path = generate_qr_code('Delivery Note', dn_number, client.client_name)
    
    story = add_company_header_to_story(story, layout_mode=layout_mode)
    
    col_padding = 0
    font_size = 9
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        leading=14,
        spaceAfter=2,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    story.append(Paragraph("DELIVERY NOTE", title_style))
    story.append(Spacer(1, 2))
    
    delivery_info = [
        ['Delivery Note Number:', dn_number],
        ['Delivery Date:', delivery_note.delivery_date.strftime('%d/%m/%Y')],
        ['Invoice Number:', inv_number],
    ]
    
    delivery_table = Table(delivery_info, colWidths=[2.5*inch, 2.5*inch])
    delivery_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
    ]))
    
    story.append(delivery_table)
    story.append(Spacer(1, 2))
    
    # Client Details
    story.append(Paragraph("DELIVERED TO:", ParagraphStyle('DeliveredTo', parent=styles['Heading3'], fontSize=10, leading=10, spaceAfter=2)))
    client_data = [
        [client.client_name],
        [Paragraph(client.address.replace('\n', '<br/>'), ParagraphStyle('ClientAddr', parent=styles['Normal'], fontSize=9, leading=10)) if client.address else ''],
        [client.phone],
    ]
    
    client_table = Table(client_data, colWidths=[5*inch])
    client_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
    ]))
    
    story.append(client_table)
    story.append(Spacer(1, 2))
    
    # Equipment Delivered
    story.append(Paragraph("EQUIPMENT DELIVERED:", ParagraphStyle('EquipDelivered', parent=styles['Heading3'], fontSize=10, leading=10, spaceAfter=2)))
    equipment_data = [
        ['Item Description', 'Quantity']
    ]
    
    for item in quotation.quotation_items:
        qty_str = f"{int(item.quantity) if item.quantity == int(item.quantity) else item.quantity}"
        if item.unit:
            qty_str += f" {item.unit}"
        equipment_data.append([
            item.project_type,
            qty_str
        ])
        
    equipment_table = Table(equipment_data, colWidths=[4*inch, 1*inch], repeatRows=1)
    equipment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
        ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),
    ]))
    
    story.append(equipment_table)
    story.append(Spacer(1, 2))
    
    # Signatures
    signature_data = [
        ['Delivered By:', 'Received By:'],
        [delivery_note.delivered_by, delivery_note.received_by or ''],
        ['_____________________', '_____________________'],
        ['Signature', 'Signature'],
        ['Date: ' + delivery_note.delivery_date.strftime('%d/%m/%Y'), 'Date: _______________'],
    ]
    
    signature_table = Table(signature_data, colWidths=[2.5*inch, 2.5*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('TOPPADDING', (0, 0), (-1, -1), col_padding),
        ('BOTTOMPADDING', (0, 0), (-1, -1), col_padding),
    ]))
    
    story.append(signature_table)
    story.append(Spacer(1, 2))
    
    story = add_signature_block(story, layout_mode=layout_mode)
    story = add_stamp_and_qr(story, dn_number, qr_path)
    story = add_hash_to_story(story, doc_hash)
    story = add_pdf_footer(story, layout_mode=layout_mode)
    build_pdf_with_numbering(doc, story)
    
    buffer.seek(0)
    secured_buffer = secure_pdf(buffer)
    
    secured_buffer.seek(0)
    response = make_response(secured_buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    safe_client = re.sub(r'[^A-Za-z0-9_]', '_', client.client_name)
    response.headers['Content-Disposition'] = f'attachment; filename=DeliveryNote_{safe_client}.pdf'
    
    return response

@finance_bp.route('/create_invoice/<int:quotation_id>')
@login_required
@admin_required
def create_invoice(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)
    items = quotation.quotation_items
    
    return render_template(
        "finance/invoices/create_invoice.html",
        quotation=quotation,
        items=items
    )

@finance_bp.route('/preview_delivery_note/<int:quotation_id>')
@login_required
@admin_required
def preview_delivery_note(quotation_id):
    quotation = Quotation.query.get_or_404(quotation_id)
    items = quotation.quotation_items
    
    return render_template(
        "finance/delivery/delivery_note.html",
        quotation=quotation,
        items=items
    )

@finance_bp.route('/delivery-approve', methods=['POST'])
@login_required
@admin_required
def approve_delivery():
    data = request.get_json()
    quotation_id = data.get('quotation_id')
    password = data.get('password')
    
    if not quotation_id or not password:
        return jsonify({'success': False, 'message': 'Missing quotation ID or password'}), 400
        
    # Verify secure password "***777xxx///A"
    expected_password = "***777xxx///A"
    # Using straight comparison as requested, or hashing if you prefer
    # To use hashlib with sha256 as shown in the prompt:
    # hashed_password = hashlib.sha256(password.encode()).hexdigest()
    # expected_hash = hashlib.sha256(expected_password.encode()).hexdigest()
    if password != expected_password:
        return jsonify({'success': False, 'message': 'Invalid Authorization Password'}), 403
        
    quotation = Quotation.query.get(quotation_id)
    if not quotation:
        return jsonify({'success': False, 'message': 'Quotation not found'}), 404
        
    try:
        # Mark as delivered
        quotation.delivery_confirmed = True
        quotation.delivery_approved_by = session.get('username')
        quotation.delivery_approved_date = datetime.utcnow()
        quotation.status = 'Delivered'
        
        # Check if contract exists, create if not
        contract = Contract.query.filter_by(quotation_id=quotation.quotation_id).first()
        if not contract:
            contract = Contract(
                quotation_id=quotation.quotation_id,
                contract_date=date.today(),
                start_date=date.today(),
                status='Approved'
            )
            db.session.add(contract)
            db.session.flush() # get contract_id
            
        # Check if invoice exists, create if not
        invoice = Invoice.query.filter_by(contract_id=contract.contract_id).first()
        if not invoice:
            invoice_number = f"INV{datetime.now().strftime('%Y%m%d')}{quotation.quotation_id:04d}"
            invoice = Invoice(
                quotation_id=quotation.quotation_id,
                contract_id=contract.contract_id,
                invoice_number=invoice_number,
                invoice_date=date.today(),
                due_date=date.today() + timedelta(days=14),
                amount=quotation.total_amount,
                payment_terms='Payment within 14 days',
                status='Unpaid'
            )
            db.session.add(invoice)
            db.session.flush()
            
        # Check if delivery note exists, create if not
        delivery_note = DeliveryNote.query.filter_by(invoice_id=invoice.invoice_id).first()
        if not delivery_note:
            items_desc = ", ".join([i.project_type for i in quotation.quotation_items])
            delivery_note = DeliveryNote(
                quotation_id=quotation.quotation_id,
                invoice_id=invoice.invoice_id,
                delivery_date=date.today(),
                equipment_delivered=items_desc,
                delivered_by=session.get('username'),
                status='Delivered'
            )
            db.session.add(delivery_note)
            
        quotation.invoice_generated = True
        quotation.delivery_note_generated = True
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Delivery Approved Successfully',
            'invoice_id': invoice.invoice_id,
            'delivery_note_id': delivery_note.delivery_id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
