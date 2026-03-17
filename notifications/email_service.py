from flask import current_app
from flask_mail import Mail, Message
from models import db, Notification
from datetime import datetime

mail = Mail()

def send_email_notification(client_id, subject, message, invoice_id=None):
    """Send email notification to client"""
    try:
        from models import Client
        
        client = Client.query.get(client_id)
        if not client or not client.email:
            return False, "Client not found or no email address"
        
        # Create notification record
        notification = Notification(
            client_id=client_id,
            type='Email',
            subject=subject,
            message=message,
            status='Sent',
            sent_at=datetime.utcnow()
        )
        
        db.session.add(notification)
        
        # Send email
        msg = Message(
            subject=subject,
            sender=current_app.config['MAIL_USERNAME'],
            recipients=[client.email]
        )
        
        msg.body = message
        msg.html = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h2>MPHAMVU WATER ENGINEERS</h2>
                    <p>Always Water</p>
                </div>
                <div style="background: white; padding: 30px; border: 1px solid #ddd; border-radius: 0 0 10px 10px;">
                    <h3>{subject}</h3>
                    <p>Dear {client.client_name},</p>
                    <div>{message}</div>
                    <hr style="margin: 30px 0;">
                    <div style="font-size: 12px; color: #666;">
                        <p><strong>MPHAMVU WATER ENGINEERS</strong></p>
                        <p>P.O BOX 561 Lilongwe</p>
                        <p>Call: +265 998 039 554, +265 999 678 417</p>
                        <p>Email: mphamvuwaterengineers@gmail.com</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        mail.send(msg)
        db.session.commit()
        
        return True, "Email sent successfully"
        
    except Exception as e:
        # Mark notification as failed
        notification.status = 'Failed'
        db.session.commit()
        return False, str(e)

def send_quotation_notification(quotation_id):
    """Send notification when quotation is ready"""
    try:
        from models import Quotation
        
        quotation = Quotation.query.get(quotation_id)
        if not quotation:
            return False, "Quotation not found"
        
        subject = f"Quotation {quotation.reference_number} is Ready"
        message = f"""
        Your quotation from Mphamvu Water Engineers is ready for collection.
        
        Quotation Details:
        - Reference: {quotation.reference_number}
        - Project Location: {quotation.project_location}
        - Total Amount: MK {quotation.total_amount:,.2f}
        - Valid Until: {(quotation.created_at + datetime.timedelta(days=quotation.validity_days)).strftime('%d/%m/%Y')}
        
        Please visit our office to collect your quotation or contact us for any questions.
        
        Thank you for choosing Mphamvu Water Engineers!
        """
        
        return send_email_notification(quotation.client_id, subject, message)
        
    except Exception as e:
        return False, str(e)

def send_invoice_notification(invoice_id):
    """Send notification when invoice is generated"""
    try:
        from models import Invoice
        
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return False, "Invoice not found"
        
        contract = invoice.contract
        quotation = contract.quotation
        client = quotation.client
        
        subject = f"Invoice {invoice.invoice_number} Generated"
        message = f"""
        Your invoice for the borehole project has been generated.
        
        Invoice Details:
        - Invoice Number: {invoice.invoice_number}
        - Invoice Date: {invoice.invoice_date.strftime('%d/%m/%Y')}
        - Due Date: {invoice.due_date.strftime('%d/%m/%Y')}
        - Amount: MK {invoice.amount:,.2f}
        - Payment Terms: {invoice.payment_terms}
        
        Bank Details:
        - Account Name: Mphamvu Water Engineers
        - National Bank: 1006978898
        - Standard Bank: 9100005388640
        - Branch: Capital City
        
        Please make payment before the due date to avoid any delays.
        
        Thank you for your business!
        """
        
        return send_email_notification(client.client_id, subject, message)
        
    except Exception as e:
        return False, str(e)

def send_delivery_notification(delivery_id):
    """Send notification when delivery note is generated"""
    try:
        from models import DeliveryNote
        
        delivery_note = DeliveryNote.query.get(delivery_id)
        if not delivery_note:
            return False, "Delivery note not found"
        
        invoice = delivery_note.invoice
        contract = invoice.contract
        quotation = contract.quotation
        client = quotation.client
        
        subject = f"Equipment Delivered - {delivery_note.reference_number}"
        message = f"""
        Your equipment has been delivered successfully.
        
        Delivery Details:
        - Delivery Note: {delivery_note.reference_number}
        - Delivery Date: {delivery_note.delivery_date.strftime('%d/%m/%Y')}
        - Equipment Delivered: {delivery_note.equipment_delivered}
        - Delivered By: {delivery_note.delivered_by}
        
        Thank you for choosing Mphamvu Water Engineers!
        """
        
        return send_email_notification(client.client_id, subject, message)
        
    except Exception as e:
        return False, str(e)

def send_payment_confirmation(payment_id):
    """Send notification when payment is received"""
    try:
        from models import Transaction
        
        transaction = Transaction.query.get(payment_id)
        if not transaction:
            return False, "Transaction not found"
        
        client = transaction.client
        
        subject = f"Payment Received - {transaction.reference_number}"
        message = f"""
        We have received your payment successfully.
        
        Payment Details:
        - Transaction Reference: {transaction.reference_number}
        - Amount: MK {transaction.amount:,.2f}
        - Payment Date: {transaction.payment_date.strftime('%d/%m/%Y')}
        - Payment Method: {transaction.payment_method}
        
        Thank you for your prompt payment!
        
        Best regards,
        Mphamvu Water Engineers
        """
        
        return send_email_notification(client.client_id, subject, message)
        
    except Exception as e:
        return False, str(e)

def send_payroll_notification(employee_id, payroll_month):
    """Send payslip notification to employee"""
    try:
        from models import Employee, Payroll
        
        employee = Employee.query.get(employee_id)
        if not employee or not employee.email:
            return False, "Employee not found or no email address"
        
        payroll = Payroll.query.filter_by(employee_id=employee_id, payroll_month=payroll_month).first()
        if not payroll:
            return False, "Payroll record not found"
        
        subject = f"Payslip for {payroll_month}"
        message = f"""
        Dear {employee.first_name} {employee.last_name},
        
        Your payslip for {payroll_month} is now available.
        
        Payslip Details:
        - Employment Number: {employee.employment_number}
        - Payroll Month: {payroll_month}
        - Net Salary: MK {payroll.net_salary:,.2f}
        
        Please log into the system to download your detailed payslip.
        
        If you have any questions, please contact the HR department.
        
        Best regards,
        Mphamvu Water Engineers HR Department
        """
        
        return send_email_notification(None, subject, message, employee_id=employee_id)
        
    except Exception as e:
        return False, str(e)
