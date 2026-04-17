from app import app
from db_utils import db
from models import Inventory

def migrate_farm_inventory():
    with app.app_context():
        items = Inventory.query.filter(Inventory.category.in_(['Animal Farm', 'Crop Farming'])).all()
        count = 0
        for item in items:
            item.category = 'Farm Inventory'
            count += 1
        
        db.session.commit()
        print(f"Migrated {count} inventory items to 'Farm Inventory'.")

if __name__ == '__main__':
    migrate_farm_inventory()
