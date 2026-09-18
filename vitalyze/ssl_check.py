"""SSL/TLS certificate inspection: expiry, issuer, protocol version."""

import socket
import ssl
from datetime import datetime, timezone


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
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                protocol = ssock.version()
                cipher = ssock.cipher()

        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_remaining = (not_after - datetime.now(timezone.utc)).days

        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))

        result.update({
            "success": True,
            "protocol": protocol,
            "cipher_suite": cipher[0] if cipher else None,
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
        print(f"    [x] SSL check failed: {result['error']}")
        return
    print(f"    Protocol:       {result['protocol']} ({result['cipher_suite']})")
    print(f"    Issued to:      {result['issued_to']}")
    print(f"    Issued by:      {result['issued_by']}")
    print(f"    Valid until:    {result['valid_until']} ({result['days_remaining']} days remaining)")
    if result["expiring_soon"]:
        print("    [!] Certificate expires in under 30 days")
