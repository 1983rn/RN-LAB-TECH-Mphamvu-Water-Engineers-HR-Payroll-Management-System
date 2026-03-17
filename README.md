# MPHAMVU WATER ENGINEERS - Enterprise Management System

A comprehensive HR Payroll Management System for Mphamvu Water Engineers that integrates Human Resource Management, Payroll Processing, Client & Borehole Project Management, Quotation Generation, Invoice & Delivery Note Automation, and Financial Transaction Tracking.

## Features

### 🏢 HR Management
- Employee profile management
- Department and position tracking
- Employment history
- Employee status management

### 💰 Payroll Processing
- Automated salary calculation
- Allowances and deductions management
- Tax calculations
- PDF payslip generation
- Payroll history tracking

### 📊 Attendance & Leave Management
- Daily attendance tracking
- Multiple attendance statuses (Present, Absent, Late, Half Day)
- Leave management (Annual, Sick, Emergency)
- Attendance reports and analytics

### 🤝 Client & Project Management
- Client database and contact management
- Borehole project tracking
- Project status monitoring
- Client communication history

### 📋 Quotation Generation
- Professional quotation builder
- Cost breakdown calculation
- PDF quotation generation with company branding
- Quotation validity tracking
- Client approval workflow

### 🧾 Invoice & Delivery Note Automation
- Automatic invoice generation from approved contracts
- Professional PDF invoices
- Delivery note creation
- Payment tracking
- Bank details integration

### 💳 Financial Transaction Tracking
- Complete transaction history
- Payment method tracking
- Bank account management
- Financial dashboard and reports
- Payment status monitoring

### 📧 Notification System
- Email notifications for clients
- Automated alerts for document readiness
- Payslip notifications
- Payment confirmations

### 🎨 Company Branding
- Professional document templates
- Company logo integration
- Consistent branding across all documents
- Professional PDF layouts

## Technology Stack

- **Backend**: Python with Flask
- **Database**: SQLite (with PostgreSQL support)
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Document Generation**: ReportLab for PDFs
- **Email**: Flask-Mail for notifications

## Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Setup Instructions

1. **Clone or extract the project** to your desired directory

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Navigate to the project directory**:
   ```bash
   cd "HR Payroll Management System"
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Access the system**:
   Open your web browser and go to `http://localhost:5000`

## Default Login Credentials

- **Username**: `Mphamvuwaterengineers`
- **Password**: `.org.ulandaduwe/2026/**?`

**Note**: You will be required to change the password on first login for security reasons.

## User Roles

### Administrator
- Full system control
- User management
- System configuration
- All modules access

### HR Manager
- Employee management
- Payroll processing
- Attendance tracking
- Report generation

### Employee
- View personal payslips
- View attendance records
- Limited access to personal information

## System Structure

```
mphamvu_system/
├── app.py                    # Main application file
├── config.py                 # Configuration settings
├── models.py                 # Database models
├── database.py               # Database utilities
├── requirements.txt          # Python dependencies
├── auth/                     # Authentication module
├── employees/                # Employee management
├── payroll/                  # Payroll processing
├── attendance/               # Attendance tracking
├── clients/                  # Client management
├── quotations/               # Quotation system
├── contracts/                # Contract management
├── finance/                  # Financial modules
├── notifications/            # Notification services
├── bank/                     # Bank integration
├── templates/                # HTML templates
├── static/                   # CSS, JS, images
├── documents/                # Document templates
├── uploads/                  # File uploads
└── database/                 # Database files
```

## Key Features in Detail

### Quotation System
- Create professional quotations with company branding
- Automatic cost calculation
- PDF generation with watermarks
- Client approval workflow
- Validity period tracking

### Payroll System
- Monthly payroll processing
- Tax calculations based on Malawi tax brackets
- Allowance and deduction management
- PDF payslip generation
- Payroll history and reporting

### Document Generation
All documents include:
- Company logo and branding
- Professional layouts
- Reference numbers
- Date stamps
- Bank details
- Authorized signatures

### Financial Tracking
- Transaction recording
- Payment status monitoring
- Bank account integration
- Financial dashboards
- Export capabilities

## Company Information

**MPHAMVU WATER ENGINEERS**
- Address: P.O BOX 561 Lilongwe
- Phone: +265 998 039 554, +265 999 678 417
- Email: mphamvuwaterengineers@gmail.com
- Services: Borehole drilling, Designing, supplying and installation of pumping systems, water reticulation and irrigation services

## Bank Details

- **Account Name**: Mphamvu Water Engineers
- **National Bank**: 1006978898
- **Standard Bank**: 9100005388640
- **Branch**: Capital City

## Support and Maintenance

### Database Backup
Regular database backups are recommended. The SQLite database is located at `database/system.db`.

### Security
- Password hashing implemented
- Session management
- Role-based access control
- Input validation

### Customization
- Company details can be updated in `config.py`
- Email settings configurable
- Tax brackets adjustable in payroll module
- Document templates customizable

## Troubleshooting

### Common Issues

1. **Database Error**: Ensure the database directory exists and is writable
2. **Login Issues**: Check default credentials and ensure password change on first login
3. **PDF Generation**: Verify ReportLab installation and permissions
4. **Email Issues**: Configure SMTP settings in config.py

### Performance Optimization
- Regular database maintenance
- Log file management
- Cache optimization for large datasets

## Development

### Adding New Modules
1. Create new module directory
2. Implement routes and models
3. Register blueprint in app.py
4. Add templates and static files

### Database Changes
- Use Flask-Migrate for schema changes
- Backup database before migrations
- Test changes in development environment

## License

This system is proprietary to MPHAMVU WATER ENGINEERS. All rights reserved.

## Contact

For technical support or system inquiries:
- Email: mphamvuwaterengineers@gmail.com
- Phone: +265 998 039 554, +265 999 678 417

---

**MPHAMVU WATER ENGINEERS - Always Water**
