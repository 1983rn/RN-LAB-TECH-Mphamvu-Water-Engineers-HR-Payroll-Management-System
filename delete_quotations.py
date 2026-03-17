from app import app
from models import db, Quotation, QuotationItem

# Reference numbers to delete
reference_numbers = ['QUO20260307162601', 'QUO20260307155926']

with app.app_context():
    deleted_count = 0
    
    for ref_num in reference_numbers:
        quotation = Quotation.query.filter_by(reference_number=ref_num).first()
        
        if quotation:
            print(f"Deleting quotation: {ref_num}")
            
            # Delete quotation items first
            QuotationItem.query.filter_by(quotation_id=quotation.quotation_id).delete()
            
            # Delete the quotation
            db.session.delete(quotation)
            deleted_count += 1
        else:
            print(f"Quotation not found: {ref_num}")
    
    # Commit all deletions
    db.session.commit()
    print(f"\nSuccessfully deleted {deleted_count} quotation(s)")
