"""Display helpers for quotation project location and optional GPS coordinates."""


def format_coord_pair(lat, lng, precision=6):
    """Format latitude/longitude as a parenthesized pair."""
    if lat is None or lng is None:
        return ''
    return f'({lat:.{precision}f}, {lng:.{precision}f})'


def parse_optional_coord(form, key):
    """Parse an optional latitude/longitude from a form-like mapping (empty means unset)."""
    raw = form.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def format_quotation_project_location(quotation):
    """Append decimal degrees after the textual project location when coordinates exist."""
    text = (
        getattr(quotation, "project_location", None)
        or getattr(quotation, "location", None)
        or ""
    ).strip()
    lat = getattr(quotation, "project_latitude", None)
    lng = getattr(quotation, "project_longitude", None)
    coord = format_coord_pair(lat, lng)
    if coord:
        return f"{text} {coord}".strip() if text else coord
    return text
