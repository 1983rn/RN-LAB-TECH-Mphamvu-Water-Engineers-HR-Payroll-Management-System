from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

def init_db():
    """Initialize the database with all tables and run migrations"""
    from sqlalchemy import text
    engine_name = db.engine.name
    print(f"Initializing database on engine: {engine_name}")
    
    # Create tables if they don't exist
    db.create_all()
    
    # ─── COMPREHENSIVE MIGRATION SYSTEM ───
    # This manually adds columns that were added to models after initial table creation.
    # Works for both SQLite (local) and PostgreSQL (Render).
    
    try:
        with db.engine.connect() as conn:
            # Helper to add column if it doesn't exist
            def add_column(table, column, type_str):
                try:
                    print(f"Checking {table}.{column}...")
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {type_str}"))
                    conn.commit()
                    print(f"  Successfully added {column} to {table}")
                except Exception:
                    # Column likely already exists or table doesn't exist yet
                    pass

            # 1. Employee Updates
            add_column('employees', 'date_dismissed', 'DATE')
            add_column('employees', 'bank_name', 'VARCHAR(100)')
            add_column('employees', 'account_number', 'VARCHAR(50)')
            add_column('employees', 'airtel_number', 'VARCHAR(20)')
            add_column('employees', 'tnm_mpamba_number', 'VARCHAR(20)')
            
            # 2. Quotation Updates
            gps_type = 'DOUBLE PRECISION' if engine_name == 'postgresql' else 'FLOAT'
            add_column('quotations', 'project_latitude', gps_type)
            add_column('quotations', 'project_longitude', gps_type)
            add_column('quotations', 'validity_days', 'INTEGER DEFAULT 30')
            add_column('quotations', 'description', 'TEXT')
            add_column('quotations', 'department', "VARCHAR(100) DEFAULT 'Borehole Drilling'")
            add_column('quotations', 'delivery_confirmed', 'BOOLEAN DEFAULT FALSE')
            add_column('quotations', 'delivery_approved_by', 'VARCHAR(100)')
            add_column('quotations', 'delivery_approved_date', 'TIMESTAMP')
            add_column('quotations', 'invoice_generated', 'BOOLEAN DEFAULT FALSE')
            add_column('quotations', 'delivery_note_generated', 'BOOLEAN DEFAULT FALSE')

            # 3. Department Column for all other models
            dept_tables = [
                'clients', 'contracts', 'invoices', 'delivery_notes', 
                'transactions', 'inventory', 'farm_activities', 'livestock',
                'crop_cycles', 'farm_inputs', 'farm_outputs', 'farm_expenses',
                'construction_projects', 'construction_stock'
            ]
            for table in dept_tables:
                default_dept = 'Farm' if 'farm' in table or 'livestock' in table or 'crop' in table else \
                               ('Construction' if 'construction' in table else 'Borehole Drilling')
                add_column(table, 'department', f"VARCHAR(100) DEFAULT '{default_dept}'")

            # 4. Construction Project Updates
            add_column('construction_projects', 'project_latitude', gps_type)
            add_column('construction_projects', 'project_longitude', gps_type)

            # 5. Page Authorization Updates
            add_column('page_authorizations', 'secret_code', 'VARCHAR(4)')

            # 6. Reference Number Updates (for older tables)
            for table in ['employees', 'payroll', 'attendance', 'clients', 'quotations', 
                          'contracts', 'invoices', 'delivery_notes', 'transactions', 'notifications']:
                add_column(table, 'reference_number', 'VARCHAR(50) UNIQUE')

            # 7. Custom Types Updates
            add_column('custom_project_types', 'department', "VARCHAR(100) DEFAULT 'Borehole'")
            add_column('custom_inventory_categories', 'department', "VARCHAR(100) DEFAULT 'Farm'")

    except Exception as e:
        print(f"Migration error: {e}")
        
    print("Database initialized successfully!")

def get_reference_number(prefix):
    """Generate unique reference numbers"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}{timestamp}"
