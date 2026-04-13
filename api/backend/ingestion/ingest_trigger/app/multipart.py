import base64
from email import message_from_bytes


def parse_multipart(body: bytes, content_type: str) -> dict:
    """
    Parse a multipart/form-data request body into a dict of { field_name: bytes }.

    Uses the stdlib email package to avoid external dependencies.
    Returns only parts that have a Content-Disposition with a name parameter.
    """
    msg_bytes = f"Content-Type: {content_type}\r\n\r\n".encode() + body
    msg = message_from_bytes(msg_bytes)  # use default compat32 policy — correct for MIME multipart

    files = {}
    for part in msg.iter_parts():
        cd = part.get("Content-Disposition", "")
        if "filename" in cd or "form-data" in cd:
            name = part.get_param("name", header="Content-Disposition")
            if name:
                files[name] = part.get_payload(decode=True)
    return files


def decode_body(event: dict) -> bytes:
    """
    Extract and decode the raw request body from an API Gateway v2 event.
    Handles both base64-encoded and plain string bodies.
    """
    body   = event.get("body", "")
    is_b64 = event.get("isBase64Encoded", False)

    if is_b64:
        return base64.b64decode(body)
    if isinstance(body, str):
        return body.encode()
    return body


def get_content_type(event: dict) -> str:
    headers = event.get("headers") or {}
    return headers.get("content-type", "")
