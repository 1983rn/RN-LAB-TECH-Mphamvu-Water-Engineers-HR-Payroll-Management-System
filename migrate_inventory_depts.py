import sys
import os

# Add the current directory to sys.path to import app and models
sys.path.append(os.getcwd())

from app import app
from db_utils import db
from models import Inventory

def migrate():
    with app.app_context():
        items = Inventory.query.all()
        print(f"Checking {len(items)} inventory items...")
        
        count = 0
        for item in items:
            old_dept = item.department
            new_dept = old_dept
            
            cat = item.category or ""
            name = item.asset_name or ""
            
            # 1. Farm Categories (1. to 8. or explicit farm terms)
            if any(cat.startswith(str(i) + ".") for i in range(1, 9)) or \
               any(term in cat.lower() for term in ['farm', 'crop', 'livestock', 'harvest']):
                new_dept = 'Farm'
                
            # 2. ICT Categories
            elif 'ICT' in cat.upper() or 'ICT' in name.upper() or 'SOFTWARE' in cat.upper():
                new_dept = 'ICT Department'
                 
            # 3. Borehole
            elif 'BOREHOLE' in cat.upper() or 'DRILLING' in cat.upper():
                new_dept = 'Borehole Drilling'
                
            # 4. Construction
            elif 'CONSTRUCTION' in cat.upper() or 'BUILDING' in cat.upper():
                new_dept = 'Construction'
            
            # 5. Lodge / Rest House
            elif 'LODGE' in cat.upper() or 'ROOM' in cat.upper() or 'BED' in cat.upper():
                new_dept = 'Lodge'

            # 6. Fallback/Defaults
            if not new_dept:
                # If category is Office Equipment, we assign to 'Borehole Drilling' as the primary entity 
                # unless specified otherwise, or keep it as is if it has a value.
                new_dept = 'Borehole Drilling'
            
            if old_dept != new_dept:
                item.department = new_dept
                print(f"Updated '{name}': [{old_dept}] -> [{new_dept}]")
                count += 1
        
        db.session.commit()
        print(f"Migration complete. {count} items updated.")

if __name__ == "__main__":
    migrate()
