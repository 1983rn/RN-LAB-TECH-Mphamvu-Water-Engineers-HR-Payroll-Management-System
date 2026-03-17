import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mphamvu_water_engineers_secret_key_2026'
    
    # Email Configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'mphamvuwaterengineers@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # SMS Configuration (for future implementation)
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    SMS_API_URL = os.environ.get('SMS_API_URL')
    
    # File Upload Configuration
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Company Information
    COMPANY_NAME = 'MPHAMVU WATER ENGINEERS'
    COMPANY_MOTTO = 'Always Water'
    COMPANY_ADDRESS = 'P.O BOX 561 Lilongwe'
    COMPANY_PHONE = '+265 998 039 554, +265 999 678 417'
    COMPANY_EMAIL = 'mphamvuwaterengineers@gmail.com'
    
    # Bank Details
    BANK_ACCOUNT_NAME = 'Mphamvu Water Engineers'
    NATIONAL_BANK_ACCOUNT = '1006978898'
    STANDARD_BANK_ACCOUNT = '9100005388640'
    BANK_BRANCH = 'Capital City'
    
    # Document Settings
    QUOTATION_VALIDITY_DAYS = 30
    INVOICE_PAYMENT_TERMS = 'Payment within 14 days'
    
    # Currency
    CURRENCY = 'MWK'
    CURRENCY_SYMBOL = 'MK'
