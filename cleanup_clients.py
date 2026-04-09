import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Client, Quotation, ClientCreditScore, Transaction, Invoice, Contract, DeliveryNote
from utils.credit_scoring import update_client_credit_score
from sqlalchemy import func

with app.app_context():
    # Group clients by lowercase name stripped
    clients = Client.query.all()
    grouped_clients = {}
    
    for c in clients:
        name_key = c.client_name.strip().lower()
        if name_key not in grouped_clients:
            grouped_clients[name_key] = []
        grouped_clients[name_key].append(c)
        
    for name_key, client_list in grouped_clients.items():
        if len(client_list) > 1:
            print(f"Found duplicates for {name_key}: {[c.client_id for c in client_list]}")
            
            # Sort by number of quotations descending, then by id descending (keep the most active/recent)
            client_list.sort(key=lambda x: (len(x.quotations), x.client_id), reverse=True)
            
            primary = client_list[0]
            duplicates = client_list[1:]
            
            for dup in duplicates:
                print(f"Merging client {dup.client_id} into {primary.client_id}")
                
                # Merge fields if missing in primary
                if not primary.phone and dup.phone:
                    primary.phone = dup.phone
                if not primary.email and dup.email:
                    primary.email = dup.email
                if not primary.address and dup.address:
                    primary.address = dup.address
                if not primary.project_type and dup.project_type:
                    primary.project_type = dup.project_type
                
                # Update quotations directly using SQLAlchemy core or flush early
                for q in Quotation.query.filter_by(client_id=dup.client_id).all():
                    q.client_id = primary.client_id
                    
                # Clean up credit score records of duplicate
                ClientCreditScore.query.filter_by(client_id=dup.client_id).delete()
                
                # Commit relations before deleting the duplicate client
                db.session.commit()
                
                # Re-fetch dup after commit
                dup = Client.query.get(dup.client_id)
                db.session.delete(dup)
                db.session.commit()
                
            db.session.commit()
            
            # Recalculate credit score for primary
            update_client_credit_score(primary.client_id)
            print(f"Successfully merged into {primary.client_id}")

    # Re-evaluate all clients
    print("Done cleaning duplicates.")
