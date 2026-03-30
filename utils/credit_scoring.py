# utils/credit_scoring.py
def normalize_score(score):
    if score >= 85:
        return 1
    elif score >= 70:
        return 2
    elif score >= 55:
        return 3
    elif score >= 40:
        return 4
    elif score >= 25:
        return 5
    else:
        return 6

def get_rating_info(normalized_score):
    mapping = {
        1: {"rating": "Excellent", "chance": "Very High", "interpretation": "Extremely Reliable Client"},
        2: {"rating": "Very Good", "chance": "Upraised", "interpretation": "Very Reliable Client"},
        3: {"rating": "Good", "chance": "Moderate", "interpretation": "Reliable Client"},
        4: {"rating": "Fair", "chance": "Low", "interpretation": "Risky Client"},
        5: {"rating": "Poor", "chance": "Very Low", "interpretation": "Very Risky Client"},
        6: {"rating": "Very Poor", "chance": "Extremely Very Low", "interpretation": "Not Reliable Client"}
    }
    return mapping.get(normalized_score, mapping[6])

def calculate_credit_score_for_client(client_id):
    from models import Client, Transaction, Quotation, Invoice, Contract
    from db_utils import db
    from datetime import datetime
    
    client = Client.query.get(client_id)
    if not client:
        return None
        
    score = 0
    
    # 1. Payment History (25%)
    # Ratio of completely paid invoices to total invoices
    invoices = Invoice.query.filter_by(quotation_id=Quotation.quotation_id).join(Quotation).filter(Quotation.client_id == client_id).all()
    # Alternatively, direct association if changed
    invoices = Invoice.query.join(Contract).join(Quotation).filter(Quotation.client_id == client_id).all() + Invoice.query.filter_by(contract_id=None).join(Quotation).filter(Quotation.client_id == client_id).all()
    # Since invoice->contract->quotation->client is complex, let's look at transactions vs quotation amount
    total_billed = client.quotation_amount or 0
    total_paid = sum(t.amount for t in client.transactions)
    
    if total_billed > 0:
        payment_ratio = min((total_paid / total_billed) * 100, 100)
    else:
        payment_ratio = 100 if total_paid > 0 else 50 # Default middle ground if no bills yet
        
    score += payment_ratio * 0.25
    
    # 2. Revenue Consistency (15%)
    # Based on number of transactions
    tx_count = len(client.transactions)
    if tx_count >= 5:
        consistency = 100
    elif tx_count >= 3:
        consistency = 80
    elif tx_count >= 1:
        consistency = 60
    else:
        consistency = 30
    score += consistency * 0.15
    
    # 3. Outstanding Balances (20%) -> (100 - ratio) * 0.20
    if total_billed > 0:
        outstanding_ratio = max(0, min(((total_billed - total_paid) / total_billed) * 100, 100))
    else:
        outstanding_ratio = 0
    score += (100 - outstanding_ratio) * 0.20
    
    # 4. Transaction Volume (10%)
    # Relative to a baseline, say 5,000,000 MWK gets 100 points
    volume_score = min((total_paid / 5000000) * 100, 100)
    score += volume_score * 0.10
    
    # 5. Credit Utilization (15%) -> (100 - utilization) * 0.15
    # Let's say utilization is outstanding_ratio
    credit_utilization = outstanding_ratio
    score += (100 - credit_utilization) * 0.15
    
    # 6. Business Age (10%)
    # Time since first created
    days_since_creation = (datetime.utcnow() - client.created_at).days
    if days_since_creation > 365:
        age_score = 100
    elif days_since_creation > 180:
        age_score = 80
    elif days_since_creation > 90:
        age_score = 60
    else:
        age_score = 40
    score += age_score * 0.10
    
    # 7. Track Record (5%)
    # Are there any completed contracts/deliveries?
    deliveries = db.session.query(db.func.count()).select_from(Quotation).join(Client).filter(Client.client_id == client_id, Quotation.delivery_confirmed == True).scalar()
    track_record = min((deliveries / max(len(client.quotations), 1)) * 100, 100) if len(client.quotations) > 0 else 50
    score += track_record * 0.05
    
    # Calculate final normalized
    normalized = normalize_score(score)
    rating_info = get_rating_info(normalized)
    
    return {
        "raw_score": round(score, 2),
        "normalized_score": normalized,
        "rating": rating_info["rating"],
        "repayment_chance": rating_info["chance"],
        "interpretation": rating_info["interpretation"]
    }

def update_client_credit_score(client_id):
    from models import ClientCreditScore
    from db_utils import db
    
    calc = calculate_credit_score_for_client(client_id)
    if not calc:
        return None
        
    credit_record = ClientCreditScore.query.filter_by(client_id=client_id).first()
    if not credit_record:
        credit_record = ClientCreditScore(client_id=client_id)
        db.session.add(credit_record)
        
    credit_record.score = calc["normalized_score"]
    credit_record.rating = calc["rating"]
    credit_record.repayment_chance = calc["repayment_chance"]
    credit_record.interpretation = calc["interpretation"]
    
    db.session.commit()
    return credit_record
