from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, PageBreak, Table as _RLTable
from datetime import datetime
import os
import qrcode
import hashlib
from pypdf import PdfReader, PdfWriter

# Patch ReportLab Table.identity for Python 3.10+ compatibility
# ReportLab's Table.identity calls max() on rowHeights, which fails if they are None in Python 3.
_old_identity = _RLTable.identity
def _patched_identity(self, maxLen=None):
    try:
        return _old_identity(self, maxLen)
    except (TypeError, ValueError):
        return f"Table(nrows={self._nrows}, ncols={self._ncols})"
_RLTable.identity = _patched_identity

class NumberedCanvas(canvas.Canvas):
    """Custom canvas for page numbering and watermark"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            self.draw_watermark()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        page_num = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 50, 30, page_num)

    def draw_watermark(self):
        self.saveState()
        self.setFont("Helvetica-Bold", 60)
        self.setFillColorRGB(0.9, 0.9, 0.9, alpha=0.3)
        self.translate(A4[0]/2, A4[1]/2)
        self.rotate(45)
        self.drawCentredString(0, 0, "MPHAMVU")
        self.restoreState()

def create_numbered_doc(buffer, pagesize=A4, **kwargs):
    """Create a document with page numbering and watermark"""
    return SimpleDocTemplate(buffer, pagesize=pagesize, **kwargs)

def build_pdf_with_numbering(doc, story):
    """Build PDF with custom canvas for numbering"""
    doc.build(story, canvasmaker=NumberedCanvas)

def create_company_header(layout_mode='normal'):
    """Create a company header with the exact image"""
    styles = getSampleStyleSheet()
    
    # Path to the company header image
    image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'company_header.png')
    
    # Create header content
    header_content = []
    
    # Check if image file exists and is a valid image
    if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
        try:
            # The original image is 991x252, with an aspect ratio of approx 3.93
            # The original image is 991x252, with an aspect ratio of approx 3.93
            # We want it to be as wide as possible to be highly visible while fitting the page
            
            # Max width based on A4 width (8.27 inches) minus margins (approx 1 inch total in dense)
            max_usable_width = 7.1 * inch if layout_mode == 'dense' else 6.5 * inch
            
            img_width = max_usable_width
            img_height = img_width / 3.9325
            header_image = Image(image_path, width=img_width, height=img_height)
            header_image.hAlign = 'CENTER'
            header_content.append(header_image)
        except Exception as e:
            # If image loading fails, use text fallback
            print(f"Error loading image: {e}")
            header_content.append(create_text_header(styles))
    else:
        # Use text fallback if image doesn't exist
        header_content.append(create_text_header(styles))
    
    return header_content
    
    return header_content

def create_text_header(styles):
    """Create a text-based header as fallback"""
    # Create company name style
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Heading1'],
        fontSize=14,
        leading=18,
        spaceAfter=3,
        alignment=1,  # Center
        textColor=colors.darkblue
    )
    
    # Create motto style
    motto_style = ParagraphStyle(
        'MottoStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=13,
        spaceAfter=4,
        alignment=1,  # Center
        textColor=colors.blue
    )
    
    # Create info style
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        spaceAfter=8,
        alignment=1,  # Center
        textColor=colors.black
    )
    
    return Paragraph(
        "<b>MPHAMVU WATER ENGINEERS</b><br/>"
        "<font color='blue'><i>Always Water</i></font><br/>"
        "<font size=8>Borehole drilling, Designing, supplying and installation of pumping systems<br/>"
        "water reticulation and irrigation services<br/>"
        "P.O BOX 561 Lilongwe | Call: +265 998 039 554, +265 999 678 417 | Email: mphamvuwaterengineers@gmail.com</font>",
        info_style
    )

def add_company_header_to_story(story, layout_mode='normal'):
    """Add company header to PDF story"""
    header_content = create_company_header(layout_mode=layout_mode)
    for element in header_content:
        story.append(element)
    
    spacer_height = 12 if layout_mode == 'normal' else (8 if layout_mode == 'compact' else 2)
    story.append(Spacer(1, spacer_height))
    return story

def add_signature_block(story, signer_name="Ulanda Duwe", signer_title="Managing Director", layout_mode='normal'):
    """Add professional signature block"""
    styles = getSampleStyleSheet()
    
    top_margin = 40 if layout_mode == 'normal' else (25 if layout_mode == 'compact' else 10)
    story.append(Spacer(1, top_margin))
    
    story.append(Paragraph("Yours faithfully,", ParagraphStyle('SignOff', parent=styles['Normal'], fontSize=10 if layout_mode == 'dense' else 11, leading=12 if layout_mode == 'dense' else 14)))
    story.append(Spacer(1, 4))
    
    signature_path = os.path.join('static', 'images', 'signature.png')
    if os.path.exists(signature_path):
        sig_img = Image(signature_path, width=0.8*inch, height=0.3*inch)
        sig_img.hAlign = 'LEFT'
        story.append(sig_img)
    else:
        story.append(Spacer(1, 30))
    
    story.append(Paragraph(f"<i>{signer_name}</i>", ParagraphStyle('SignerName', parent=styles['Normal'], fontSize=10 if layout_mode == 'dense' else 11, leading=12 if layout_mode == 'dense' else 14)))
    story.append(Paragraph(f"({signer_title})", ParagraphStyle('SignerTitle', parent=styles['Normal'], fontSize=8.5 if layout_mode == 'dense' else 9.5, leading=10 if layout_mode == 'dense' else 13)))
    return story

def generate_qr_code(doc_type, doc_number, client_name, amount=None):
    """Generate QR code for document verification"""
    qr_dir = os.path.join('static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)
    
    verification_data = f"MPHAMVU WATER ENGINEERS\nDocument: {doc_type}\nNumber: {doc_number}\nClient: {client_name}"
    if amount:
        verification_data += f"\nAmount: MWK {amount:,.2f}"
    verification_data += "\nStatus: Valid"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(verification_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    qr_path = os.path.join(qr_dir, f"{doc_number}.png")
    img.save(qr_path)
    return qr_path

def add_stamp_and_qr(story, doc_number, qr_path, layout_mode='normal'):
    """Add company stamp and QR code to PDF tightly side by side"""
    
    # QR Code
    if os.path.exists(qr_path):
        qr_size = 0.7*inch if layout_mode == 'dense' else (0.8*inch if layout_mode == 'compact' else 0.9*inch)
        qr_img = Image(qr_path, width=qr_size, height=qr_size)
        qr_cell = [
            qr_img,
            Paragraph("<font size=7>Scan to Verify</font>", ParagraphStyle('QRLabel', parent=getSampleStyleSheet()['Normal'], alignment=1))
        ]
    else:
        qr_cell = [Paragraph("<font size=7>QR Code</font>", getSampleStyleSheet()['Normal'])]
    
    # Company Stamp
    stamp_path = os.path.join('static', 'images', 'company_stamp.png')
    if os.path.exists(stamp_path):
        stamp_size = 0.95*inch if layout_mode == 'dense' else (1.2*inch if layout_mode == 'compact' else 1.4*inch)
        stamp_img = Image(stamp_path, width=stamp_size, height=stamp_size)
        stamp_cell = [stamp_img]
    else:
        stamp_cell = [Paragraph("<font size=7>[COMPANY STAMP]</font>", getSampleStyleSheet()['Normal'])]
    
    # Place them in a single row layout with no massive space between them
    stamp_qr_table = Table([[stamp_cell, '', qr_cell]], colWidths=[2.5*inch, 2.0*inch, 1.5*inch])
    stamp_qr_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    spacer_height = 8 if layout_mode == 'normal' else (5 if layout_mode == 'compact' else 2)
    story.append(Spacer(1, spacer_height))
    story.append(stamp_qr_table)
    return story

def generate_document_hash(doc_number, client_name, amount=None):
    """Generate SHA-256 hash for document verification"""
    data_string = f"{doc_number}{client_name}"
    if amount:
        data_string += f"{amount}"
    return hashlib.sha256(data_string.encode()).hexdigest()

def secure_pdf(input_buffer):
    """Encrypt PDF to prevent editing and copying"""
    reader = PdfReader(input_buffer)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    writer.encrypt(
        user_password="",
        owner_password="MPHAMVU_SECURE_2026",
        permissions_flag=0b0000010000000100  # Allow printing only
    )
    
    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer

def add_hash_to_story(story, doc_hash):
    """Add verification hash to PDF"""
    styles = getSampleStyleSheet()
    hash_style = ParagraphStyle(
        'HashStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=12,
        textColor=colors.grey,
        alignment=0
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Verification Hash:</b> {doc_hash}", hash_style))
    return story

def generate_document_number(doc_type, doc_id, created_date):
    """Generate official document number: DOC-YYYY-NNN"""
    year = created_date.year
    return f"{doc_type}-{year}-{doc_id:03d}"

def add_pdf_footer(story, layout_mode='normal'):
    """Add developer footer to PDF"""
    styles = getSampleStyleSheet()
    
    font_size = 8.5 if layout_mode == 'normal' else (8.2 if layout_mode == 'compact' else 8)
    margin_top = 10 if layout_mode == 'normal' else (7 if layout_mode == 'compact' else 4)
    
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=font_size,
        leading=11,
        alignment=1,
        textColor=colors.grey
    )
    
    story.append(Spacer(1, margin_top))
    story.append(Paragraph(
        f"Generated by RN-LAB-TECH-SOLUTIONS | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        footer_style
    ))
    return story

# --- ID Card Generation ---

# Standard CR80 ID Card dimensions (2.125" x 3.375")
CR80_WIDTH = 2.125 * inch
CR80_HEIGHT = 3.375 * inch

def generate_employee_qr(employee):
    """Generate QR code specifically for an ID Card"""
    qr_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)
    
    verification_data = f"MPHAMVU WATER ENGINEERS\nEmployee: {employee.first_name} {employee.last_name}\nID: {employee.employment_number}\nDept: {employee.department}\nStatus: {employee.status}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(verification_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    qr_path = os.path.join(qr_dir, f"EMP_{employee.employment_number.replace('/', '_')}.png")
    img.save(qr_path)
    return qr_path



def create_id_card_front(employee, styles):
    """Create the front face of an ID card as a Table flowable"""
    
    # Adjusted sizes to fit within ReportLab frames (which seem to have 6pt margins default)
    SAFE_WIDTH = CR80_WIDTH - 12
    SAFE_HEIGHT = CR80_HEIGHT - 12

    # 1. Header (Blue Bar)
    header_data = [[Paragraph("MPHAMVU WATER<br/>ENGINEERS", styles['IDTitle'])]]
    header_table = Table(header_data, colWidths=[SAFE_WIDTH], rowHeights=[0.4*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.darkblue),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    
    # 2. Employee Photo
    photo_elements = []
    if employee.photo_path:
        photo_abs = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', employee.photo_path.replace('/', os.sep))
        if os.path.exists(photo_abs):
            try:
                emp_img = Image(photo_abs, width=1.1*inch, height=1.1*inch)
                img_table = Table([[emp_img]], colWidths=[SAFE_WIDTH])
                img_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ]))
                photo_elements.append(img_table)
            except Exception:
                photo_elements.append(Paragraph("[Photo Error]", styles['IDEmpDetails']))
        else:
            photo_elements.append(Paragraph("[Missing]", styles['IDEmpDetails']))
    else:
        photo_elements.append(Paragraph("[No Photo]", styles['IDEmpDetails']))
        
    # 3. Employee Name & Details
    details_data = [
        [Spacer(1, 4)],
        [Paragraph(f"{employee.first_name} {employee.last_name}".upper(), styles['IDEmpName'])],
        [Spacer(1, 2)],
        [Paragraph(f"<b>{employee.position}</b>", styles['IDEmpDetails'])],
        [Paragraph(f"{employee.department}", styles['IDEmpDetails'])],
        [Spacer(1, 6)],
        [Paragraph(f"ID: <b>{employee.employment_number}</b>", styles['IDEmpDetails'])]
    ]
    
    # Assemble card exactly to CR80 height constraints
    card_data = [
        [header_table],
        [Spacer(1, 8)],
        [photo_elements[0]],
        [Table(details_data, colWidths=[SAFE_WIDTH], style=TableStyle([
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))]
    ]
    
    # Main card table
    card = Table(card_data, colWidths=[SAFE_WIDTH], rowHeights=[
        0.4*inch, 
        8, 
        1.1*inch, 
        None # Let it adjust
    ])
    
    card.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    
    return card

def create_id_card_back(employee, styles):
    """Create the back face of an ID card as a Table flowable"""
    
    SAFE_WIDTH = CR80_WIDTH - 12
    SAFE_HEIGHT = CR80_HEIGHT - 12

    back_data = [
        [Spacer(1, 12)],
        [Paragraph("MPHAMVU WATER ENGINEERS", styles['IDBackTitle'])],
        [Paragraph("<i>Always Water</i>", styles['IDBackTitle'])],
        [Spacer(1, 4)],
        [Paragraph(
            "P.O BOX 561 Lilongwe<br/>"
            "Call: +265 998 039 554<br/>"
            "mphamvuwaterengineers@gmail.com", 
            styles['IDBackText']
        )],
        [Spacer(1, 12)]
    ]
    
    # QR Code
    qr_path = generate_employee_qr(employee)
    if os.path.exists(qr_path):
        qr_img = Image(qr_path, width=0.85*inch, height=0.85*inch)
        qr_table = Table([[qr_img]], colWidths=[SAFE_WIDTH])
        qr_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        back_data.append([qr_table])
        back_data.append([Spacer(1, 8)])
    else:
        back_data.append([Spacer(1, 1*inch)])
    
    back_data.append([Paragraph("This card is property of Mphamvu Water Engineers. If found, please return to the address above.", styles['IDBackText'])])
    back_data.append([Spacer(1, 6)])
    back_data.append([Paragraph("SAFETY FIRST", styles['IDSafety'])])
    
    card = Table(back_data, colWidths=[SAFE_WIDTH])
    card.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    
    return card

def _add_id_styles(styles):
    """Helper to inject styles safely if they don't exist"""
    try:
        styles.add(ParagraphStyle(
            name='IDTitle', parent=styles['Normal'], fontSize=10, leading=12,
            alignment=1, textColor=colors.white, fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='IDEmpName', parent=styles['Normal'], fontSize=12, leading=14,
            alignment=1, fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='IDEmpDetails', parent=styles['Normal'], fontSize=8, leading=10, alignment=1
        ))
        styles.add(ParagraphStyle(
            name='IDBackTitle', parent=styles['Normal'], fontSize=10, leading=12,
            alignment=1, fontName='Helvetica-Bold', textColor=colors.darkblue
        ))
        styles.add(ParagraphStyle(
            name='IDBackText', parent=styles['Normal'], fontSize=6, leading=8, alignment=1
        ))
        styles.add(ParagraphStyle(
            name='IDSafety', parent=styles['Normal'], fontSize=8, leading=10,
            alignment=1, fontName='Helvetica-Bold', textColor=colors.red
        ))
    except ValueError:
        pass # Already added

def generate_dual_sided_id_card(employee):
    """Generate a dual-sided CR80 ID card for an employee"""
    buffer = BytesIO()
    
    # Setup document with exact CR80 size and zero margins
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=(CR80_WIDTH, CR80_HEIGHT),
        rightMargin=0, 
        leftMargin=0, 
        topMargin=0, 
        bottomMargin=0
    )
    
    story = []
    styles = getSampleStyleSheet()
    _add_id_styles(styles)
    
    story.append(create_id_card_front(employee, styles))
    story.append(PageBreak())
    story.append(create_id_card_back(employee, styles))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_bulk_id_cards(employees):
    """
    Generate an A4 mass-printable PDF containing all ID cards.
    Layout: 3 columns x 3 rows per page (9 cards per page).
    Page 1: Fronts, Page 2: Backs (mirrored for duplex printing).
    """
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, # Standard A4 Portrait (8.27" x 11.69")
        rightMargin=0.5*inch, 
        leftMargin=0.5*inch, 
        topMargin=0.5*inch, 
        bottomMargin=0.5*inch
    )
    
    story = []
    styles = getSampleStyleSheet()
    _add_id_styles(styles)
    
    # Layout configuration
    COLS = 3 # 3 columns safely fits on A4 Portrait (3 x 2.125" = 6.375" / 8.27")
    ROWS = 3 # 3 rows safely fits on A4 Portrait (3 x 3.375" = 10.125" / 11.69")
    CARDS_PER_PAGE = COLS * ROWS
    
    for i in range(0, len(employees), CARDS_PER_PAGE):
        batch = employees[i:i+CARDS_PER_PAGE]
        
        # --- DRAW FRONTS ---
        front_grid = []
        for r in range(ROWS):
            row_data = []
            for c in range(COLS):
                idx = r * COLS + c
                if idx < len(batch):
                    row_data.append(create_id_card_front(batch[idx], styles))
                else:
                    row_data.append('') # Empty cell
            front_grid.append(row_data)
            
        # Add slight spacing between cards manually
        front_table = Table(front_grid, colWidths=[CR80_WIDTH]*COLS, rowHeights=[CR80_HEIGHT]*ROWS)
        front_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        
        story.append(Paragraph(f"Mass ID Printing - Fronts - Page {i//CARDS_PER_PAGE + 1}", styles['Normal']))
        story.append(Spacer(1, 10))
        story.append(front_table)
        story.append(PageBreak())
        
        # --- DRAW BACKS (Mirrored for duplex) ---
        back_grid = []
        for r in range(ROWS):
            row_data = []
            for c in range(COLS):
                # MIRROR LOGIC: If a card is at column `c` on the front, 
                # to print duplex correctly over the short edge, it must be at column `COLS - 1 - c` on the back.
                mirrored_col = COLS - 1 - c
                idx = r * COLS + mirrored_col
                
                if idx < len(batch):
                    row_data.append(create_id_card_back(batch[idx], styles))
                else:
                    row_data.append('')
            back_grid.append(row_data)
            
        back_table = Table(back_grid, colWidths=[CR80_WIDTH]*COLS, rowHeights=[CR80_HEIGHT]*ROWS)
        back_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        
        story.append(Paragraph(f"Mass ID Printing - Backs - Page {i//CARDS_PER_PAGE + 1} (Mirrored)", styles['Normal']))
        story.append(Spacer(1, 10))
        story.append(back_table)
        story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer

