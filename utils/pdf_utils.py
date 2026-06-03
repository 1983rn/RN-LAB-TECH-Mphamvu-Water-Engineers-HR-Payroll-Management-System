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
import io

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
        self.qr_path = None

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            self.draw_watermark()
            self.draw_qr_code_fixed()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        page_num = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 50, 30, page_num)

    def draw_qr_code_fixed(self):
        if self.qr_path and os.path.exists(self.qr_path):
            qr_size = 0.8 * inch
            # Draw at bottom right, slightly above the footer
            self.drawImage(self.qr_path, A4[0] - qr_size - 40, 45, width=qr_size, height=qr_size)
            self.setFont("Helvetica-Bold", 6)
            self.setFillColor(colors.darkblue)
            self.drawCentredString(A4[0] - (qr_size/2) - 40, 40, "SCAN TO VERIFY")

    def draw_watermark(self):
        self.saveState()
        self.setFont("Helvetica-Bold", 60)
        self.setFillColorRGB(0.9, 0.9, 0.9, alpha=0.3)
        self.translate(A4[0]/2, A4[1]/2)
        self.rotate(45)
        self.drawCentredString(0, 0, "DRAFT")
        self.restoreState()

def create_numbered_doc(buffer, pagesize=A4, **kwargs):
    """Create a document with page numbering and watermark"""
    return SimpleDocTemplate(buffer, pagesize=pagesize, **kwargs)

def build_pdf_with_numbering(doc, story, qr_path=None):
    """Build PDF with custom canvas for numbering and optional QR code"""
    def canvas_wrapper(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.qr_path = qr_path
        return c
    doc.build(story, canvasmaker=canvas_wrapper)

def create_company_header(layout_mode='normal'):
    """Create a company header with the exact image"""
    styles = getSampleStyleSheet()

    # Path to the company header image
    image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'mphamvu_attached_logo.png')

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
        "<b>YOUR COMPANY NAME</b><br/>"
        "<font color='blue'><i>Your Tagline</i></font><br/>"
        "<font size=8>Your business description<br/>"
        "Your services<br/>"
        "Your contact information</font>",
        info_style
    )

def add_company_header_to_story(story, layout_mode='normal', department=None):
    """Add company header to PDF story, with optional department subtitle"""
    header_content = create_company_header(layout_mode=layout_mode)
    for element in header_content:
        story.append(element)

    # Add department name below header if provided
    if department:
        styles = getSampleStyleSheet()
        dept_style = ParagraphStyle(
            'DeptHeader',
            parent=styles['Normal'],
            fontSize=11 if layout_mode == 'normal' else (10 if layout_mode == 'compact' else 9),
            leading=14,
            alignment=1,  # Center
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#003366'),
            spaceBefore=2,
            spaceAfter=2,
        )
        story.append(Paragraph(f"Department: {department}", dept_style))

    spacer_height = 8 if layout_mode == 'normal' else (4 if layout_mode == 'compact' else 2)
    story.append(Spacer(1, spacer_height))
    return story

def add_signature_block(story, signer_name="", signer_title="", layout_mode='normal'):
    """Add professional signature block"""
    styles = getSampleStyleSheet()

    top_margin = 20 if layout_mode == 'normal' else (15 if layout_mode == 'compact' else 8)
    story.append(Spacer(1, top_margin))

    story.append(Paragraph("Yours faithfully,", ParagraphStyle('SignOff', parent=styles['Normal'], fontSize=10 if layout_mode == 'dense' else 11, leading=12 if layout_mode == 'dense' else 14)))
    story.append(Spacer(1, 2))

    signature_path = os.path.join('static', 'images', 'signature.png')
    if os.path.exists(signature_path):
        sig_img = Image(signature_path, width=0.8*inch, height=0.3*inch)
        sig_img.hAlign = 'LEFT'
        story.append(sig_img)
    else:
        story.append(Spacer(1, 30))

    if signer_name:
        story.append(Paragraph(f"<i>{signer_name}</i>", ParagraphStyle('SignerName', parent=styles['Normal'], fontSize=10 if layout_mode == 'dense' else 11, leading=12 if layout_mode == 'dense' else 14)))
    if signer_title:
        story.append(Paragraph(f"({signer_title})", ParagraphStyle('SignerTitle', parent=styles['Normal'], fontSize=8.5 if layout_mode == 'dense' else 9.5, leading=10 if layout_mode == 'dense' else 13)))
    return story

def generate_qr_code(doc_type, doc_number, client_name, amount=None, month=None):
    """Generate QR code for document verification"""
    qr_dir = os.path.join('static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)

    verification_data = f"Company: Mphamvu\nDocument: {doc_type}\nNumber: {doc_number}\nClient: {client_name}"
    if month:
        verification_data += f"\nMonth: {month}"
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
    """Legacy function, redirecting to the combined layout function"""
    return story

def add_signature_stamp_qr(story, doc_number, qr_path, layout_mode='normal', signer_name="", signer_title=""):
    """Add professional signature block, stamp, and QR code in a single horizontal row"""
    styles = getSampleStyleSheet()

    top_margin = 20 if layout_mode == 'normal' else (15 if layout_mode == 'compact' else 8)
    story.append(Spacer(1, top_margin))

    # --- Signature Block Flowables ---
    sig_cell = []
    sig_cell.append(Paragraph("Yours faithfully,", ParagraphStyle('SignOff', parent=styles['Normal'], fontSize=10 if layout_mode == 'dense' else 11, leading=12 if layout_mode == 'dense' else 14)))
    sig_cell.append(Spacer(1, 2))

    signature_path = os.path.join('static', 'images', 'signature.png')
    if os.path.exists(signature_path):
        sig_img = Image(signature_path, width=0.8*inch, height=0.3*inch)
        sig_img.hAlign = 'LEFT'
        sig_cell.append(sig_img)
    else:
        sig_cell.append(Spacer(1, 30))

    if signer_name:
        sig_cell.append(Paragraph(f"<i>{signer_name}</i>", ParagraphStyle('SignerName', parent=styles['Normal'], fontSize=10 if layout_mode == 'dense' else 11, leading=12 if layout_mode == 'dense' else 14)))
    if signer_title:
        sig_cell.append(Paragraph(f"({signer_title})", ParagraphStyle('SignerTitle', parent=styles['Normal'], fontSize=8.5 if layout_mode == 'dense' else 9.5, leading=10 if layout_mode == 'dense' else 13)))

    # --- QR Code ---
    if os.path.exists(qr_path):
        qr_size = 0.7*inch if layout_mode == 'dense' else (0.8*inch if layout_mode == 'compact' else 0.9*inch)
        qr_img = Image(qr_path, width=qr_size, height=qr_size)
        qr_cell = [
            qr_img,
            Paragraph("<font size=7>Scan to Verify</font>", ParagraphStyle('QRLabel', parent=styles['Normal'], alignment=1))
        ]
    else:
        qr_cell = [Paragraph("<font size=7>QR Code</font>", styles['Normal'])]

    # --- Company Stamp (Increased size as requested) ---
    stamp_path = os.path.join('static', 'images', 'company_stamp.png')
    if os.path.exists(stamp_path):
        # Increased size per user request
        stamp_size = 1.1*inch if layout_mode == 'dense' else (1.3*inch if layout_mode == 'compact' else 1.5*inch)
        stamp_img = Image(stamp_path, width=stamp_size, height=stamp_size)
        stamp_cell = [stamp_img]
    else:
        stamp_cell = [Paragraph("<font size=7>[COMPANY STAMP]</font>", styles['Normal'])]

    # --- Assemble the Table ---
    # Widths apportioned: 2.2 inch for sig, 2.5 inch for stamp, 1.5 inch for QR
    stamp_qr_table = Table([[sig_cell, stamp_cell, qr_cell]], colWidths=[2.2*inch, 2.5*inch, 1.5*inch])
    stamp_qr_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),      # Signature aligned left
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),    # Stamp centered
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),     # QR Code right aligned
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), # Align bottom to keep them grounded
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    spacer_height = 4 if layout_mode == 'normal' else (3 if layout_mode == 'compact' else 2)
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
    """Generate official document number: DOC-YYYY-MM-NNN"""
    if created_date is None:
        created_date = datetime.now()
    year = created_date.year
    month = created_date.strftime('%m')
    return f"{doc_type}-{year}-{month}-{doc_id:03d}"

def add_pdf_footer(story, layout_mode='normal'):
    """Add developer footer to PDF"""
    styles = getSampleStyleSheet()

    font_size = 8.5 if layout_mode == 'normal' else (8.2 if layout_mode == 'compact' else 8)
    margin_top = 4 if layout_mode == 'normal' else (3 if layout_mode == 'compact' else 2)

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

    verification_data = f"YOUR COMPANY\nEmployee: {employee.first_name} {employee.last_name}\nID: {employee.employment_number}\nDept: {employee.department}\nStatus: {employee.status}"

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
    header_data = [[Paragraph("YOUR<br/>COMPANY", styles['IDTitle'])]]
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
        [Paragraph("YOUR COMPANY", styles['IDBackTitle'])],
        [Paragraph("<i>Your Tagline</i>", styles['IDBackTitle'])],
        [Spacer(1, 4)],
        [Paragraph(
            "Your Address<br/>"
            "Your Phone<br/>"
            "Your Email",
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

    back_data.append([Paragraph("This card is property of Your Company. If found, please return to the address above.", styles['IDBackText'])])
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


def generate_receipt_pdf(transaction, department=None):
    """Generate a premium payment receipt PDF"""
    buffer = io.BytesIO()
    doc = create_numbered_doc(buffer, pagesize=A4)
    story = []

    # 1. Company Header
    story = add_company_header_to_story(story, layout_mode='normal', department=department or 'Accounts Department')

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=1, spaceAfter=20, textColor=colors.darkblue)
    story.append(Paragraph("OFFICIAL PAYMENT RECEIPT", title_style))

    # 2. Receipt Info Table
    receipt_no = f"REC-{datetime.now().year}-{transaction.transaction_id:04d}"
    info_data = [
        [Paragraph(f"<b>Receipt No:</b> {receipt_no}", styles['Normal']),
         Paragraph(f"<b>Date:</b> {transaction.payment_date.strftime('%d/%m/%Y')}", styles['Normal'])]
    ]
    info_table = Table(info_data, colWidths=[3*inch, 3*inch])
    info_table.setStyle(TableStyle([('ALIGN', (1,0), (1,0), 'RIGHT')]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # 3. Payment Details
    styles.add(ParagraphStyle('DetailLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10))
    styles.add(ParagraphStyle('DetailValue', parent=styles['Normal'], fontSize=11, leading=14))

    details = [
        [Paragraph("Received From:", styles['DetailLabel']), Paragraph(transaction.client.client_name if transaction.client else "N/A", styles['DetailValue'])],
        [Paragraph("Amount Received:", styles['DetailLabel']), Paragraph(f"MWK {transaction.amount:,.2f}", styles['DetailValue'])],
        [Paragraph("Payment Method:", styles['DetailLabel']), Paragraph(transaction.payment_method, styles['DetailValue'])],
        [Paragraph("Reference:", styles['DetailLabel']), Paragraph(transaction.transaction_reference or "N/A", styles['DetailValue'])],
        [Paragraph("Being Payment For:", styles['DetailLabel']), Paragraph(transaction.notes or f"Payment for Invoice {transaction.invoice.invoice_number if transaction.invoice else 'N/A'}", styles['DetailValue'])]
    ]

    details_table = Table(details, colWidths=[1.5*inch, 4.5*inch], rowHeights=25)
    details_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 30))

    # 4. Professional Stamp & Signature Area
    qr_path = generate_qr_code("RECEIPT", receipt_no, transaction.client.client_name if transaction.client else "N/A", transaction.amount)
    story = add_signature_stamp_qr(story, receipt_no, qr_path)

    # 5. Footer
    story = add_pdf_footer(story)

    # Build
    doc.build(story, canvasmaker=NumberedCanvas)

    # Secure and return
    pdf_out = buffer.getvalue()
    buffer.close()
    return io.BytesIO(pdf_out)

def generate_general_receipt_pdf(data):
    """Generate the General Receipt PDF imitating the physical format"""
    buffer = io.BytesIO()

    # Custom tight page size or landscape A5 might be closer to physical receipt,
    # but let's stick to standard layout with nice formatting (half letter or custom)
    RECEIPT_WIDTH = 8 * inch
    RECEIPT_HEIGHT = 5.5 * inch
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(RECEIPT_WIDTH, RECEIPT_HEIGHT),
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    story = []
    styles = getSampleStyleSheet()

    # --- Title ---
    title_style = ParagraphStyle(
        'ReceiptTitle', parent=styles['Heading2'], alignment=TA_CENTER,
        fontName='Helvetica-BoldOblique', fontSize=12, spaceAfter=15
    )
    story.append(Paragraph("CASH RECEIPT", title_style))

    # --- Header (Logo and Company Info) ---
    company_name = data.get('company', '')
    tagline = ""
    specialists = ""
    contact_info = "<b>Your Address<br/>Your City</b><br/><br/>Call: <b>Your Phone</b><br/><br/><font size=7 color='blue'>Your Email</font>"

    # Configure info based on company selected
    if 'Water Engineers' in company_name:
        tagline = "<font color='#0099cc'><i>\"Always Water\"</i></font>"
        specialists = "<b>Specialists in:</b> Borehole drilling, Designing, supplying and installation of pumping systems, water reticulation and irrigation services"
    elif 'Construction' in company_name:
        tagline = "<font color='#ff6600'><i>\"Building the Future\"</i></font>"
        specialists = "<b>Specialists in:</b> Building & Civil Construction"
    elif 'Farm' in company_name:
        tagline = "<font color='#33cc33'><i>\"Fresh & Natural\"</i></font>"
        specialists = "<b>Specialists in:</b> Agricultural Production & Livestock"
    elif 'Lodge' in company_name:
        tagline = "<font color='#993333'><i>\"Your Home Away from Home\"</i></font>"
        specialists = "<b>Specialists in:</b> Hospitality & Accommodation"
    elif 'ICT' in company_name:
        tagline = "<font color='#3333cc'><i>\"Tech Solutions Delivered\"</i></font>"
        specialists = "<b>Specialists in:</b> IT Solutions & Software Development"

    # Logo
    logo_path = os.path.join('static', 'images', 'receipt_logo.png')
    logo = ""
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=1.5*inch, height=1.5*inch)

    # Company Header formatting
    comp_header_style = ParagraphStyle('CompName', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, spaceAfter=2)
    tag_style = ParagraphStyle('CompTag', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, spaceAfter=8)
    spec_style = ParagraphStyle('CompSpec', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-BoldOblique')

    mid_col = [
        Paragraph(company_name.upper(), comp_header_style),
        Paragraph(tagline, tag_style),
        Paragraph(specialists, spec_style)
    ]

    right_col = Paragraph(contact_info, ParagraphStyle('Contact', parent=styles['Normal'], fontSize=9, leading=11))

    header_table = Table([[logo, mid_col, right_col]], colWidths=[2.0*inch, 3.2*inch, 1.8*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
    ]))
    story.append(header_table)

    # Add a thin line under header
    story.append(Spacer(1, 10))
    story.append(Table([['']], colWidths=[7*inch], style=[('LINEABOVE', (0,0), (-1,0), 1, colors.grey)]))
    story.append(Spacer(1, 5))

    # --- Meta Info (TIN, Receipt No, Date) ---
    tin = data.get('tin', '31872543')
    receipt_no = data.get('receipt_number', '0001')
    date_str = data.get('date', '...')

    tin_p = Paragraph(f"<b>TIN: {tin}</b>", ParagraphStyle('TinStyle', parent=styles['Normal'], fontSize=11))
    tin_table = Table([[tin_p]], colWidths=[1.5*inch])
    tin_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))

    meta_table = Table([[
        tin_table,
        Paragraph(f"<b>RECEIPT No. <font color='red'>{receipt_no}</font></b>", ParagraphStyle('RecNo', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER)),
        Paragraph(f"<b>Date:</b> <u> {date_str} </u>", ParagraphStyle('DateP', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT))
    ]], colWidths=[2.0*inch, 2.5*inch, 2.5*inch])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # --- Form Fields ---
    def dotted_line_text(label, value):
        # HTML formatting for underline look
        return Paragraph(
            f"<b><i>{label}</i></b> <u> {value} </u>",
            ParagraphStyle('Field', parent=styles['Normal'], fontSize=11, leading=16)
        )

    story.append(dotted_line_text("Received From:", data.get('received_from', '')))
    story.append(Spacer(1, 8))
    story.append(dotted_line_text("The sum of:", data.get('sum_of_words', '')))
    story.append(Spacer(1, 8))
    story.append(dotted_line_text("Being paid for:", data.get('payment_for', '')))
    story.append(Spacer(1, 15))

    # --- Amount & Signature ---
    amount_str = f"<b>MWK</b> {float(data.get('amount', 0)):,.2f}"
    amt_p = Paragraph(amount_str, ParagraphStyle('AmtStyle', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER))
    amt_table = Table([[amt_p]], colWidths=[1.8*inch])
    amt_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))

    sig_path = os.path.join('static', 'images', 'signature.png')
    sig_img = ""
    if os.path.exists(sig_path):
        sig_img = Image(sig_path, width=0.8*inch, height=0.3*inch)

    sig_col = [
        Paragraph("<b><i>With thanks</i></b>", ParagraphStyle('SigThanks', parent=styles['Normal'], fontSize=10, fontName='Helvetica-BoldOblique')),
        sig_img if sig_img else Spacer(1, 0.3*inch),
    ]

    bottom_table = Table([[amt_table, sig_col]], colWidths=[4*inch, 3*inch])
    bottom_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(bottom_table)
    story.append(Spacer(1, 10))

    # Cash/Check No & for Company
    last_line = Table([[
        Paragraph(f"<b><i>Cash / Check No.:</i></b> <u> {data.get('payment_method', 'Cash')} </u>", ParagraphStyle('LLine', parent=styles['Normal'], fontSize=11)),
        Paragraph(f"for {company_name}", ParagraphStyle('ForCo', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT))
    ]], colWidths=[3.5*inch, 3.5*inch])
    story.append(last_line)

    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>******This is an electronically produced receipt******</i>", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)))

    # Build PDF
    doc.build(story)

    buffer.seek(0)
    return buffer


def generate_dynamic_rfq_pdf(form_data, company_document_paths=None):
    """
    Generate a professional RFQ Response PDF from the dynamic form data.
    Optimized to fit all content on a single A4 page with QR code at bottom-right.

    Args:
        form_data: dict with keys like company, contact, phone, email, reg_no,
                   water_reg_no, location, work_required, table_data, yield,
                   warranty_borehole, warranty_pump, days_to_complete,
                   deposit, balance_condition, validity_days.
                   table_data is a dict with 'headers', 'rows', 'footer'.
        company_document_paths: Optional path or list of paths to company documents
                                  (PDF/images/DOC/DOCX). PDFs/images will be appended to the
                                  end of the generated PDF; DOC/DOCX will be listed on a final page.

    Returns:
        BytesIO buffer containing the generated PDF.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.35 * inch,
        bottomMargin=0.4 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch
    )

    styles = getSampleStyleSheet()
    story = []

    # ---- Reusable Styles (Dense / single-page optimized) ----
    title_style = ParagraphStyle(
        'RFQTitle', parent=styles['Heading1'],
        fontSize=13, leading=15, alignment=1,  # Center
        textColor=colors.HexColor('#003366'), spaceAfter=1, spaceBefore=0
    )

    section_style = ParagraphStyle(
        'RFQSection', parent=styles['Heading2'],
        fontSize=9.5, leading=11, spaceAfter=2, spaceBefore=3,
        textColor=colors.HexColor('#003366'),
        borderWidth=0, borderPadding=0
    )

    label_style = ParagraphStyle(
        'RFQLabel', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=colors.HexColor('#333333')
    )

    value_style = ParagraphStyle(
        'RFQValue', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=colors.black
    )

    small_style = ParagraphStyle(
        'RFQSmall', parent=styles['Normal'],
        fontSize=7, leading=8.5, textColor=colors.grey
    )

    # RFQ reference code style
    ref_style = ParagraphStyle(
        'RFQRef', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=2,  # Right-aligned
        textColor=colors.HexColor('#003366'), fontName='Helvetica-Bold'
    )

    # ---- Dynamic Company Header (Image Logo - Dense mode) ----
    department = form_data.get('department', '')
    add_company_header_to_story(story, layout_mode='dense', department=department)

    # Title
    story.append(Paragraph('<b>QUOTATION / RESPONSE TO REQUEST FOR QUOTATION</b>', title_style))

    # RFQ Reference Code & Date on same line
    rfq_ref = form_data.get('reference_number', '')
    date_str = datetime.now().strftime('%d %B %Y')
    time_str = datetime.now().strftime('%H:%M')

    if rfq_ref:
        ref_date_data = [
            [Paragraph(f'<b>Ref:</b> {rfq_ref}', value_style),
             Paragraph(f'<b>Date:</b> {date_str}', ParagraphStyle('DateRight', parent=styles['Normal'], fontSize=8, leading=10, alignment=2))],
        ]
        ref_date_table = Table(ref_date_data, colWidths=[3.5*inch, 3.5*inch])
        ref_date_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(ref_date_table)
    else:
        story.append(Paragraph(f'<b>Date:</b> {date_str}', value_style))
    story.append(Spacer(1, 2))
    # ---- 1. Client Details ----
    story.append(Paragraph('<b>1. Client Details</b>', section_style))

    client_data = [
        ['Client Name:', form_data.get('company', ''), 'Contact:', form_data.get('contact', '')],
        ['Phone:', form_data.get('phone', ''), 'Email:', form_data.get('email', '')],
        ['Address:', form_data.get('reg_no', ''), 'Other Info:', form_data.get('water_reg_no', '')],
    ]

    client_table = Table(client_data, colWidths=[1.0*inch, 2.5*inch, 1.0*inch, 2.5*inch])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#003366')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#003366')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#dddddd')),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 2))

    # ---- 2. Scope of Work ----
    story.append(Paragraph('<b>2. Scope of Work</b>', section_style))

    location = form_data.get('location', '')
    work_required = form_data.get('work_required', '')

    scope_data = [
        [Paragraph('<b>Location:</b>', label_style), Paragraph(location, value_style)],
        [Paragraph('<b>Work Required:</b>', label_style), Paragraph(work_required, value_style)],
    ]
    scope_table = Table(scope_data, colWidths=[1.1*inch, 5.9*inch])
    scope_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(scope_table)
    story.append(Spacer(1, 2))

    # ---- 3. Itemized Costs (Dynamic Table) ----
    story.append(Paragraph('<b>3. Itemized Costs</b>', section_style))

    table_info = form_data.get('table_data', {})
    headers = table_info.get('headers', [])
    rows = table_info.get('rows', [])
    footer = table_info.get('footer', [])

    # Enforce a maximum of 6 columns for RFQ layout to match UI and PDF expectations
    num_cols = min(len(headers) if headers else 6, 6)

    # Trim or pad headers to exactly num_cols
    if headers:
        headers = (headers + [''] * num_cols)[:num_cols]
    else:
        # Default to standard 6-column RFQ headers
        headers = ['Item', 'Description', 'Unit', 'Qty', 'Unit Rate', 'Total'][:num_cols]

    # Build table data with Paragraphs for word wrapping
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=9.5)
    header_cell_style = ParagraphStyle('HeaderCellStyle', parent=styles['Normal'], fontSize=8, leading=9.5, textColor=colors.white)

    pdf_table_data = []

    # Header row
    pdf_header = [Paragraph(f'<b>{h}</b>', header_cell_style) for h in headers]
    pdf_table_data.append(pdf_header)

    import html
    # Body rows
    for row in rows:
        # Pad or trim each row to match num_cols
        padded_row = list(row) + [''] * max(0, num_cols - len(row))
        pdf_row = [Paragraph(html.escape(str(cell)), cell_style) for cell in padded_row[:num_cols]]
        pdf_table_data.append(pdf_row)

    # Footer row (Grand Total)
    if footer:
        # Build footer such that the label spans all but the last column and the value is in the last column
        label_text = footer[0] if len(footer) >= 1 and footer[0] else 'GRAND TOTAL'
        total_text = footer[-1] if len(footer) >= 2 else ''

        # Align label text to right (alignment=2 is right-align)
        footer_label_style = ParagraphStyle('FooterLabelStyle', parent=styles['Normal'], fontSize=8.5, leading=10, alignment=2)
        footer_value_style = ParagraphStyle('FooterValueStyle', parent=styles['Normal'], fontSize=8.5, leading=10, alignment=0)

        footer_row = [Paragraph(f'<b>{label_text}</b>', footer_label_style)] + [Paragraph('', cell_style)] * max(0, num_cols - 2) + [Paragraph(f'<b>{total_text}</b>', footer_value_style)]
        # Ensure footer_row has exactly num_cols elements
        footer_row = (footer_row + [Paragraph('', cell_style)] * num_cols)[:num_cols]
        pdf_table_data.append(footer_row)

    # Calculate column widths dynamically
    available_width = 7.0 * inch
    if num_cols == 6:
        # Standard RFQ layout: Item, Description, Unit, Qty, Unit Rate, Total
        col_widths = [0.4*inch, 2.4*inch, 0.6*inch, 0.5*inch, 1.3*inch, 1.3*inch]
    elif num_cols <= 5:
        # Default layout: Item narrow, Description wide, rest equal
        col_widths = [0.5*inch, 2.8*inch] + [(available_width - 3.3*inch) / max(1, num_cols - 2)] * max(0, num_cols - 2)
    else:
        col_widths = [available_width / num_cols] * num_cols

    # Ensure col_widths matches num_cols exactly
    col_widths = col_widths[:num_cols]

    items_table = Table(pdf_table_data, colWidths=col_widths, repeatRows=1)

    # Styles for the table
    table_style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#999999')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f4f8')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]

    # Footer row styling (last row if footer exists)
    if footer:
        last_idx = len(pdf_table_data) - 1
        table_style_cmds.extend([
            ('BACKGROUND', (0, last_idx), (-1, last_idx), colors.HexColor('#e6ecf0')),
            ('FONTNAME', (0, last_idx), (-1, last_idx), 'Helvetica-Bold'),
            ('SPAN', (0, last_idx), (-2, last_idx)),  # Span label across all but last column
        ])

    items_table.setStyle(TableStyle(table_style_cmds))
    story.append(items_table)
    story.append(Spacer(1, 2))

    # ---- 4. Technical Details (conditional on department) ----
    department = form_data.get('department', 'Borehole')
    non_borehole_depts = ['Construction', 'Farm', 'Lodge', 'ICT Department']
    is_borehole = department not in non_borehole_depts

    # Helper to safely format a value with a unit suffix, avoiding duplicates
    def format_unit(value, unit_str):
        if not value:
            return ''
        val = str(value).strip()
        if not val:
            return ''
        # Avoid duplicating the unit if user already typed it
        if val.lower().endswith(unit_str.lower().strip()):
            return val
        return f'{val} {unit_str}'

    if is_borehole:
        # Full technical details for Borehole Drilling
        story.append(Paragraph('<b>4. Technical Details</b>', section_style))

        tech_data = [
            ['Min Yield:', format_unit(form_data.get('yield_value', ''), 'liters/sec'),
             'Warranty (Borehole):', format_unit(form_data.get('warranty_borehole', ''), 'years')],
            ['Warranty (Pump):', format_unit(form_data.get('warranty_pump', ''), 'years'),
             'Days to Complete:', format_unit(form_data.get('days_to_complete', ''), 'days')],
        ]

        tech_table = Table(tech_data, colWidths=[1.3*inch, 2.2*inch, 1.3*inch, 2.2*inch])
        tech_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#003366')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#003366')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#dddddd')),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
        ]))
        story.append(tech_table)
        story.append(Spacer(1, 2))
    else:
        # For non-borehole departments, only show Days to Complete if provided
        days_val = form_data.get('days_to_complete', '')
        if days_val:
            story.append(Paragraph('<b>4. Technical Details</b>', section_style))
            tech_data = [
                ['Days to Complete:', format_unit(days_val, 'days'), '', ''],
            ]
            tech_table = Table(tech_data, colWidths=[1.3*inch, 2.2*inch, 1.3*inch, 2.2*inch])
            tech_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#003366')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#dddddd')),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
            ]))
            story.append(tech_table)
            story.append(Spacer(1, 2))

    # ---- 5. Payment Terms & Validity ----
    story.append(Paragraph('<b>5. Payment Terms &amp; Validity</b>', section_style))

    deposit = form_data.get('deposit', '')
    balance = form_data.get('balance_condition', '')
    validity = form_data.get('validity_days', '')

    payment_data = [
        ['Deposit Required:', f'{deposit}%' if deposit else '',
         'Balance Paid:', balance if balance else ''],
        ['Quotation Valid For:', f'{validity} days' if validity else '', '', ''],
    ]

    payment_table = Table(payment_data, colWidths=[1.3*inch, 2.2*inch, 1.3*inch, 2.2*inch])
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#003366')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#003366')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#dddddd')),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 3))

    # ---- 6. ATTACHMENTS REQUIRED ----
    story.append(Paragraph('<b>6. ATTACHMENTS REQUIRED</b>', section_style))
    story.append(Paragraph('Attached are copies of company\'s certificates', value_style))
    story.append(Spacer(1, 3))

    # ---- Signature Block + Company Stamp + QR Code (combined horizontal layout) ----
    # Parse signer name and title from form_data['contact']
    contact_text = form_data.get('contact', '')
    signer_name = ""
    signer_title = ""
    if '(' in contact_text and ')' in contact_text:
        parts = contact_text.split('(')
        signer_name = parts[0].strip()
        signer_title = parts[1].replace(')', '').strip()
    elif contact_text:
        signer_name = contact_text.strip()
        signer_title = ""

    # Auto-generate the current date and time
    from datetime import datetime as _dt
    current_date = _dt.now().strftime('%d %B %Y')
    current_time = _dt.now().strftime('%H:%M:%S')

    # --- Build Signature Cell (left) ---
    sig_cell_contents = []
    sig_cell_contents.append(Paragraph("<b>Signed:</b>", cell_style))

    signature_path = os.path.join('static', 'images', 'signature.png')
    if os.path.exists(signature_path):
        sig_img = Image(signature_path, width=0.9*inch, height=0.3*inch)
        sig_img.hAlign = 'LEFT'
        sig_cell_contents.append(sig_img)
    else:
        sig_cell_contents.append(Paragraph("___________________________", cell_style))

    sig_cell_contents.append(Paragraph(f"<b>Name:</b> {signer_name}", cell_style))
    if signer_title:
        sig_cell_contents.append(Paragraph(f"<b>Position:</b> {signer_title}", cell_style))
    sig_cell_contents.append(Paragraph(f"<b>Date:</b> {current_date}", cell_style))

    # --- Build Company Stamp Cell (center) ---
    stamp_path = os.path.join('static', 'images', 'company_stamp.png')
    stamp_cell_contents = []
    if os.path.exists(stamp_path):
        stamp_img = Image(stamp_path, width=1.0*inch, height=1.0*inch)
        stamp_cell_contents.append(stamp_img)
    else:
        stamp_cell_contents.append(Paragraph("<font size=7>[COMPANY STAMP]</font>", styles['Normal']))

    # --- Build QR Code Cell (right) ---
    # Generate QR code for this RFQ document
    rfq_doc_number = rfq_ref if rfq_ref else f"RFQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    client_name = form_data.get('company', 'Unknown Client')
    qr_path = generate_qr_code("RFQ", rfq_doc_number, client_name)

    qr_cell_contents = []
    if os.path.exists(qr_path):
        qr_img = Image(qr_path, width=0.7*inch, height=0.7*inch)
        qr_cell_contents.append(qr_img)
        qr_cell_contents.append(Paragraph("<font size=6><b>SCAN TO VERIFY</b></font>",
            ParagraphStyle('QRLabel', parent=styles['Normal'], alignment=1, fontSize=6, leading=8)))
    else:
        qr_cell_contents.append(Paragraph("<font size=7>QR Code</font>", styles['Normal']))

    # --- Assemble Signature + Stamp + QR in one row ---
    sig_stamp_qr_table = Table(
        [[sig_cell_contents, stamp_cell_contents, qr_cell_contents]],
        colWidths=[2.8*inch, 2.2*inch, 2.0*inch]
    )
    sig_stamp_qr_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),       # Signature aligned left
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),      # Stamp centered
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),       # QR Code right aligned
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),   # All aligned to bottom
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(sig_stamp_qr_table)
    story.append(Spacer(1, 3))

    # ---- Dynamic Footer with RFQ Code ----
    footer_line = f'Generated by Mphamvu ICT Department \u2014 {current_time} {current_date}'
    if rfq_ref:
        footer_line += f'  |  Ref: {rfq_ref}'

    # Horizontal rule
    from reportlab.platypus import HRFlowable
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#cccccc'), spaceAfter=2, spaceBefore=2))

    story.append(Paragraph(
        f'<i>{footer_line}</i>',
        ParagraphStyle('RFQFooterNote', parent=styles['Normal'],
                       fontSize=7, leading=8, alignment=1, textColor=colors.HexColor('#666666'))
    ))

    # Build the main PDF
    doc.build(story)

    # Append company documents (PDF/images) as an appendix
    if company_document_paths:
        try:
            if isinstance(company_document_paths, (str, bytes)):
                company_document_paths = [company_document_paths]

            document_paths = [p for p in company_document_paths if p and os.path.exists(p)]
            if document_paths:
                buffer.seek(0)
                main_reader = PdfReader(buffer)
                writer = PdfWriter()

                # Add all pages from the generated PDF
                for page in main_reader.pages:
                    writer.add_page(page)

                for doc_path in document_paths:
                    ext = os.path.splitext(doc_path)[1].lower()
                    base_name = os.path.basename(doc_path)

                    if ext == '.pdf':
                        appendix_reader = PdfReader(doc_path)
                        for page in appendix_reader.pages:
                            writer.add_page(page)
                    elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
                        # Convert image to a PDF page and append
                        img_buffer = BytesIO()
                        img_doc = SimpleDocTemplate(
                            img_buffer,
                            pagesize=A4,
                            topMargin=0.5 * inch,
                            bottomMargin=0.5 * inch,
                            leftMargin=0.5 * inch,
                            rightMargin=0.5 * inch,
                        )
                        img_story = []
                        img_story.append(
                            Paragraph(
                                '<b>Appendix: Company Documents</b>',
                                ParagraphStyle(
                                    'AppTitle',
                                    parent=styles['Heading2'],
                                    fontSize=13,
                                    alignment=1,
                                    spaceAfter=8,
                                    textColor=colors.HexColor('#003366'),
                                ),
                            )
                        )
                        img_story.append(Paragraph(f'<b>File:</b> {base_name}', small_style))
                        img_story.append(Spacer(1, 8))

                        max_w = 7.0 * inch
                        max_h = 9.0 * inch
                        img = Image(doc_path, width=max_w, height=max_h)
                        img.hAlign = 'CENTER'
                        img_story.append(img)
                        img_doc.build(img_story)

                        img_buffer.seek(0)
                        img_reader = PdfReader(img_buffer)
                        for page in img_reader.pages:
                            writer.add_page(page)
                    else:
                        # DOC/DOCX (or unknown types): include a listing page
                        note_buffer = BytesIO()
                        note_doc = SimpleDocTemplate(
                            note_buffer,
                            pagesize=A4,
                            topMargin=0.5 * inch,
                            bottomMargin=0.5 * inch,
                            leftMargin=0.5 * inch,
                            rightMargin=0.5 * inch,
                        )
                        note_story = []
                        note_story.append(
                            Paragraph(
                                '<b>Appendix: Company Documents</b>',
                                ParagraphStyle(
                                    'AppTitle',
                                    parent=styles['Heading2'],
                                    fontSize=13,
                                    alignment=1,
                                    spaceAfter=8,
                                    textColor=colors.HexColor('#003366'),
                                ),
                            )
                        )
                        note_story.append(Paragraph(f'<b>File:</b> {base_name}', small_style))
                        note_story.append(
                            Paragraph(
                                'This document type could not be automatically appended to the PDF. '
                                'Please download the attachment for full contents.',
                                ParagraphStyle('DocNote', parent=styles['Normal'], fontSize=9, leading=11),
                            )
                        )
                        note_doc.build(note_story)

                        note_buffer.seek(0)
                        note_reader = PdfReader(note_buffer)
                        for page in note_reader.pages:
                            writer.add_page(page)

                combined_buffer = BytesIO()
                writer.write(combined_buffer)
                combined_buffer.seek(0)
                return combined_buffer

        except Exception as e:
            # If appending fails, return the main PDF without the appendix
            print(f"Warning: Could not append company documents: {e}")
            buffer.seek(0)
            return buffer

    buffer.seek(0)
    return buffer
