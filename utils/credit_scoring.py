# utils/credit_scoring.py

def get_credit_rating(score):
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Very Reliable"
    elif score >= 60:
        return "Reliable"
    elif score >= 40:
        return "Moderate"
    elif score >= 20:
        return "Risk"
    else:
        return "High Risk"

def calculate_credit_score(client):
    points = (
        (client.completed_transactions or 0) * 10
        + (client.on_time_payments or 0) * 5
        - (client.defaults or 0) * 20
    )
    return points

def update_client_credit_score(client_id):
    from models import Client, Transaction
    from db_utils import db
    
    client = Client.query.get(client_id)
    if not client:
        return None
        
    # Dynamically recount completed transactions if they exist in DB
    completed_tx = Transaction.query.filter_by(client_id=client_id, status='Completed').count()
    total_tx = Transaction.query.filter_by(client_id=client_id).count()
    
    # If the database reflects transactions, sync them:
    if total_tx > 0:
        client.total_transactions = total_tx
        client.completed_transactions = completed_tx
        
    client.credit_score = calculate_credit_score(client)
    db.session.commit()
    
    return client
