import json
from datetime import datetime, timedelta

from models import db, RFQRequest, RFQResponse


# Fingerprints used to identify hardcoded sample RFQ responses.
_HARDCODED_FINGERPRINTS = [
    'Hydrogeological Survey',
    'Mobilization & Demobilization',
    'Mobilization &amp; Demobilization',
    'Drilling (45m depth)',
    'Drilling – estimate 60m depth',
    'Casing & Screen Installation',
    'Casing &amp; Screen Installation',
    'Test Pumping',
]

_HARDCODED_COMPANIES = [
    'Apostolic Faith Mission Church',
    'Mphamvu Water Engineers',
    'MPHAMVU WATER ENGINEERS',
]


def _is_sample_rfq_response(rfq: RFQResponse) -> bool:
    # Check company name match
    if rfq.company and rfq.company.strip() in _HARDCODED_COMPANIES:
        return True

    # Check table_data for fingerprints
    if rfq.table_data:
        try:
            raw = rfq.table_data if isinstance(rfq.table_data, str) else json.dumps(rfq.table_data)
            return any(fp in raw for fp in _HARDCODED_FINGERPRINTS)
        except Exception:
            return False

    return False


def _is_sample_rfq_request(rfq: RFQRequest) -> bool:
    hay = f"{rfq.client or ''} {rfq.location or ''} {rfq.item or ''} {rfq.description or ''}"
    hay_lower = hay.lower()

    if rfq.client and rfq.client.strip() in _HARDCODED_COMPANIES:
        return True

    for fp in _HARDCODED_FINGERPRINTS:
        if fp.lower() in hay_lower:
            return True

    return False


def cleanup_hardcoded_rfq_records(*, recent_only_minutes: int | None = None) -> dict:
    """
    Deletes hardcoded/sample RFQ records that should not exist in production.

    Returns basic deletion counts for logging/diagnostics.
    """
    result = {
        "deleted_rfq_requests": 0,
        "deleted_rfq_responses": 0,
    }

    now = datetime.utcnow()
    cutoff = None
    if recent_only_minutes is not None:
        cutoff = now - timedelta(minutes=recent_only_minutes)

    # Cleanup RFQ Responses (quotation/rfq_response documents)
    q_resp = RFQResponse.query
    if cutoff is not None:
        q_resp = q_resp.filter(RFQResponse.created_at >= cutoff)

    to_delete_resp = []
    for rfq in q_resp.all():
        if _is_sample_rfq_response(rfq):
            to_delete_resp.append(rfq)

    if to_delete_resp:
        for rfq in to_delete_resp:
            db.session.delete(rfq)
        result["deleted_rfq_responses"] = len(to_delete_resp)

    # Cleanup RFQ Requests (automated/parsing inbox requests)
    q_req = RFQRequest.query
    if cutoff is not None:
        q_req = q_req.filter(RFQRequest.created_at >= cutoff)

    to_delete_req = []
    for rfq in q_req.all():
        if _is_sample_rfq_request(rfq):
            to_delete_req.append(rfq)

    if to_delete_req:
        for rfq in to_delete_req:
            db.session.delete(rfq)
        result["deleted_rfq_requests"] = len(to_delete_req)

    if to_delete_req or to_delete_resp:
        db.session.commit()

    return result

