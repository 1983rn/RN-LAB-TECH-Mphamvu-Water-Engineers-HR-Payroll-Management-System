from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def init_db():
    """Initialize the database with all tables and run migrations"""
    from sqlalchemy import text
    engine_name = db.engine.name
    print(f"--- DATABASE INITIALIZATION START ({engine_name}) ---")
    
    # Create tables if they don't exist
    try:
        db.create_all()
        print("  Basic tables created/verified.")
    except Exception as e:
        print(f"  Error in create_all: {e}")
    
    # ─── COMPREHENSIVE MIGRATION SYSTEM ───
    # This manually adds columns that were added to models after initial table creation.
    # Uses individual transactions for each column to ensure one failure doesn't stop others.
    
    def add_column_if_missing(table, column, type_str):
        # We use a nested transaction or separate connection to avoid transaction aborts
        try:
            with db.engine.begin() as conn:
                # Check if column exists (PostgreSQL specific check, or just try and catch)
                if engine_name == 'postgresql':
                    # More reliable check for PostgreSQL
                    check_query = text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' AND column_name='{column}'")
                    result = conn.execute(check_query).fetchone()
                    if result:
                        return # Already exists
                
                print(f"  Migrating {table}.{column}...")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {type_str}"))
                print(f"    Added {column} to {table}")
        except Exception as e:
            # Silence expected errors (like column already exists) but log others if needed
            if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                print(f"    Migration skipped for {table}.{column}: {e}")

    # 1. Employee Updates
    add_column_if_missing('employees', 'date_dismissed', 'DATE')
    add_column_if_missing('employees', 'bank_name', 'VARCHAR(100)')
    add_column_if_missing('employees', 'account_number', 'VARCHAR(50)')
    add_column_if_missing('employees', 'airtel_number', 'VARCHAR(20)')
    add_column_if_missing('employees', 'tnm_mpamba_number', 'VARCHAR(20)')
    
    # 2. Quotation Updates
    gps_type = 'DOUBLE PRECISION' if engine_name == 'postgresql' else 'FLOAT'
    add_column_if_missing('quotations', 'project_latitude', gps_type)
    add_column_if_missing('quotations', 'project_longitude', gps_type)
    add_column_if_missing('quotations', 'validity_days', 'INTEGER DEFAULT 30')
    add_column_if_missing('quotations', 'description', 'TEXT')
    add_column_if_missing('quotations', 'department', "VARCHAR(100) DEFAULT 'Borehole Drilling'")
    add_column_if_missing('quotations', 'delivery_confirmed', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('quotations', 'delivery_approved_by', 'VARCHAR(100)')
    add_column_if_missing('quotations', 'delivery_approved_date', 'TIMESTAMP')
    add_column_if_missing('quotations', 'invoice_generated', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('quotations', 'delivery_note_generated', 'BOOLEAN DEFAULT FALSE')

    # 3. Department Column for other models
    dept_tables = [
        'clients', 'contracts', 'invoices', 'delivery_notes', 
        'transactions', 'inventory', 'farm_activities', 'livestock',
        'crop_cycles', 'farm_inputs', 'farm_outputs', 'farm_expenses',
        'construction_projects', 'construction_stock'
    ]
    for table in dept_tables:
        default_dept = 'Farm' if 'farm' in table or 'livestock' in table or 'crop' in table else \
                       ('Construction' if 'construction' in table else 'Borehole Drilling')
        add_column_if_missing(table, 'department', f"VARCHAR(100) DEFAULT '{default_dept}'")

    # 4. Construction Project Updates
    add_column_if_missing('construction_projects', 'project_latitude', gps_type)
    add_column_if_missing('construction_projects', 'project_longitude', gps_type)

    # 5. Page Authorization Updates
    add_column_if_missing('page_authorizations', 'secret_code', 'VARCHAR(4)')

    # 6. Reference Number Updates
    for table in ['employees', 'payroll', 'attendance', 'clients', 'quotations', 
                  'contracts', 'invoices', 'delivery_notes', 'transactions', 'notifications']:
        add_column_if_missing(table, 'reference_number', 'VARCHAR(50) UNIQUE')

    # 7. Custom Types Updates
    add_column_if_missing('custom_project_types', 'department', "VARCHAR(100) DEFAULT 'Borehole'")
    add_column_if_missing('custom_inventory_categories', 'department', "VARCHAR(100) DEFAULT 'Farm'")

    print("--- DATABASE INITIALIZATION COMPLETE ---")
        
    print("Database initialized successfully!")

def get_reference_number(prefix):
    """Generate unique reference numbers"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}{timestamp}"
