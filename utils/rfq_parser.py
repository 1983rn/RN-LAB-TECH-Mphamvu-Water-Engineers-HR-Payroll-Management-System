import imaplib
import email
import re
import os
import logging
from datetime import datetime, timedelta
from threading import Thread
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_field(text, field_name):
    """
    Extracts the value of a specific field from semi-structured text.
    Assumes format 'Field Name: Value' or 'Field Name - Value'
    """
    pattern = rf"(?i){field_name}[\s]*[:\-][\s]*(.+?)(?=\n[A-Za-z]+[\s]*[:\-]|&)"
    match = re.search(pattern, text + "\n&")  # Append '&' as EOF marker
    if match:
        return match.group(1).strip()
    return ""

def calculate_total(qty_str, rate_str):
    try:
        qty = float(qty_str.replace(',', '')) if qty_str else 0.0
        rate = float(rate_str.replace(',', '')) if rate_str else 0.0
        return qty * rate
    except Exception:
        return 0.0

def process_rfq_text(text, source):
    """
    Parses RFQ text and creates an RFQRequest in the DB.
    """
    from models import db, RFQRequest
    from app import app
    
    with app.app_context():
        try:
            # Parse basic logic
            client = extract_field(text, "Client")
            location = extract_field(text, "Location")
            item = extract_field(text, "Item")
            description = extract_field(text, "Description")
            unit = extract_field(text, "Unit")
            
            qty_str = extract_field(text, "Qty")
            rate_str = extract_field(text, "Unit Rate")
            
            # If no client was parsed, it might not be an RFQ format we support. Skip or dump to description.
            if not client and not item:
                logger.warning(f"Ignored unmatched RFQ text from {source}: {text[:50]}")
                return False
                
            qty = float(qty_str.replace(',', '')) if qty_str else None
            unit_rate = float(rate_str.replace(',', '')) if rate_str else None
            total = calculate_total(qty_str, rate_str)
            
            def _norm(s):
                return (s or '').strip().lower()

            def _flt(v):
                if v is None:
                    return None
                try:
                    return round(float(v), 6)
                except Exception:
                    return None

            # Dedupe: avoid inserting the same RFQ multiple times due to webhook retries
            # or background re-processing.
            recent_cutoff = datetime.utcnow() - timedelta(minutes=15)
            existing_recent = (
                RFQRequest.query.filter(
                    RFQRequest.source == source,
                    RFQRequest.created_at >= recent_cutoff,
                )
                .all()
            )

            target = {
                "client": _norm(client),
                "location": _norm(location),
                "item": _norm(item),
                "description": _norm(description),
                "unit": _norm(unit),
                "qty": _flt(qty),
                "unit_rate": _flt(unit_rate),
            }

            for r in existing_recent:
                candidate = {
                    "client": _norm(r.client),
                    "location": _norm(r.location),
                    "item": _norm(r.item),
                    "description": _norm(r.description),
                    "unit": _norm(r.unit),
                    "qty": _flt(r.qty),
                    "unit_rate": _flt(r.unit_rate),
                }
                if candidate == target:
                    logger.info(
                        f"Skipping duplicate RFQ parse for source={source}, client={client}"
                    )
                    return False

            rfq = RFQRequest(
                client=client,
                location=location,
                item=item,
                description=description,
                unit=unit,
                qty=qty,
                unit_rate=unit_rate,
                total=total,
                source=source,
                status='pending'
            )

            db.session.add(rfq)
            db.session.commit()
            logger.info(f"Successfully processed RFQ from {source} for client: {client}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {source} RFQ: {str(e)}")
            return False

def fetch_emails():
    """
    Connects to Gmail via IMAP and looks for requested quotations
    """
    from app import app
    with app.app_context():
        email_address = "mphamvuwaterengineers@gmail.com"
        # Fallback to an env variable but since the user provided it, we can hardcode for this script
        # However password MUST come from env.
        app_password = os.environ.get('EMAIL_APP_PASSWORD')
        
        if not app_password:
            logger.debug("EMAIL_APP_PASSWORD not set, skipping IMAP fetch.")
            return

        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email_address, app_password)
            mail.select("inbox")

            # Search for unread emails (you could also look for specific subjects)
            status, messages = mail.search(None, 'UNSEEN')
            
            if status != "OK":
                return
                
            msg_ids = messages[0].split()
            if not msg_ids:
                return
                
            for num in msg_ids:
                _, msg_data = mail.fetch(num, "(RFC822)")
                raw_email = msg_data[0][1]
                if not isinstance(raw_email, bytes):
                    continue
                msg = email.message_from_bytes(raw_email)

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body = payload.decode(errors='ignore')
                else:
                    payload = msg.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode(errors='ignore')

                if body:
                    processed = process_rfq_text(body, source="email")
                    # Mark as seen only if we successfully created an RFQ request.
                    # This prevents re-processing the same unread email on every loop.
                    if processed:
                        try:
                            mail.store(num, '+FLAGS', '\\Seen')
                        except Exception as e:
                            logger.debug(f"Could not mark email as seen: {e}")
                    
        except Exception as e:
            logger.error(f"IMAP Fetch Error: {str(e)}")

def start_background_task():
    """
    Starts the daemon thread that checks emails every 60 seconds
    """
    def task_loop():
        # Delay the first execution to let Flask startup complete fully
        time.sleep(10)
        while True:
            fetch_emails()
            time.sleep(60)

    thread = Thread(target=task_loop, daemon=True)
    thread.start()
    logger.info("Background Email RFQ Fetcher started.")
