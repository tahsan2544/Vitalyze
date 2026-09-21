"""SSL/TLS certificate inspection: expiry, issuer, protocol version."""

import socket
import ssl
from datetime import datetime, timezone

from . import colors


def run(netloc: str, timeout: int = 10) -> dict:
    host = netloc.split(":")[0]
    port = 443
    if ":" in netloc:
        try:
            port = int(netloc.split(":")[1])
        except ValueError:
            pass

    result = {"host": host, "success": False, "error": None}

    try:
        ctx = ssl.create_default_context()
        # Advertise HTTP/2 support via ALPN so we can see what the server
        # actually negotiates — an objective fact, not a guess.
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                protocol = ssock.version()
                cipher = ssock.cipher()
                alpn_protocol = ssock.selected_alpn_protocol()

        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_remaining = (not_after - datetime.now(timezone.utc)).days

        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))

        result.update({
            "success": True,
            "protocol": protocol,
            "cipher_suite": cipher[0] if cipher else None,
            "alpn_protocol": alpn_protocol,
            "http2_supported": alpn_protocol == "h2",
            "issued_to": subject.get("commonName"),
            "issued_by": issuer.get("organizationName") or issuer.get("commonName"),
            "valid_from": not_before.isoformat(),
            "valid_until": not_after.isoformat(),
            "days_remaining": days_remaining,
            "expiring_soon": days_remaining < 30,
        })
    except (socket.timeout, socket.gaierror, ConnectionRefusedError, ssl.SSLError, OSError) as e:
        result["error"] = str(e)

    return result


def print_result(result: dict) -> None:
    if not result["success"]:
        message = f"SSL check failed: {result['error']}"
        print(f"    {colors.bad(message)}")
        return
    if result["days_remaining"] < 0:
        print(f"    {colors.bad('Certificate has expired')}")
    elif result["expiring_soon"]:
        print(f"    {colors.warn('Certificate expires soon')}")
    else:
        print(f"    {colors.ok('Certificate valid')}")
    print(f"    Protocol:       {result['protocol']} ({result['cipher_suite']})")
    http2_text = colors.ok("yes") if result["http2_supported"] else "no"
    print(f"    HTTP/2:         {http2_text}")
    print(f"    Issued to:      {result['issued_to']}")
    print(f"    Issued by:      {result['issued_by']}")
    print(f"    Valid until:    {result['valid_until']} ({result['days_remaining']} days remaining)")
