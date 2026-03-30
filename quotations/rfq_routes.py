from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from models import db, RFQRequest
from utils.rfq_parser import process_rfq_text
from functools import wraps
import os

rfq_bp = Blueprint('rfq', __name__, url_prefix='/rfq')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['Administrator', 'HR Manager']:
            flash('Administrator access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@rfq_bp.route('/pending')
@login_required
@admin_required
def list_pending():
    # Show recently pending RFQs or even processed ones for history
    rfqs = RFQRequest.query.order_by(RFQRequest.created_at.desc()).all()
    return render_template('quotations/rfq_list.html', rfqs=rfqs)

@rfq_bp.route('/webhook', methods=['GET', 'POST'])
def facebook_webhook():
    if request.method == 'GET':
        verify_token = os.environ.get('FB_VERIFY_TOKEN', '')
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode and token:
            if mode == "subscribe" and token == verify_token:
                return challenge, 200
            else:
                return "Forbidden", 403
        return "Not configured", 400

    if request.method == 'POST':
        data = request.json
        if data and data.get("object") == "page":
            for entry in data.get('entry', []):
                for msg in entry.get('messaging', []):
                    if 'message' in msg and 'text' in msg['message']:
                        text = msg['message'].get('text')
                        # Log message sender here if needed: sender_id = msg['sender']['id']
                        process_rfq_text(text, source="facebook")
            return "OK", 200
        return "Not Found", 404
