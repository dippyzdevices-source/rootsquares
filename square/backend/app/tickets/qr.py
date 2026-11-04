import base64
from io import BytesIO

import qrcode


def generate_qr_data_url(data: str) -> str:
    """Encodes an opaque string (a Ticket.ticket_code — never customer data, per PRD §21)
    as a QR code PNG, returned as a base64 data URI for direct <img> use."""
    image = qrcode.make(data)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
