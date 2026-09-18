"""
Granular, phase-by-phase HTTP timing — the precision upgrade over a single
"total time" number.

Instead of one round-trip time, this breaks a request into the phases that
actually make it up:

    DNS lookup -> TCP connect -> TLS handshake (https only) -> TTFB -> download

It does this by subclassing http.client's HTTPConnection/HTTPSConnection
and instrumenting their connect() method directly, then using putrequest/
getresponse (the same protocol-correct parsing `http.client` normally uses)
so status lines, headers, chunked transfer-encoding, etc. are handled
properly rather than hand-parsed.

"TTFB" here means: time until the response status line + headers have been
fully received (the point where getresponse() returns) — the standard
approximation used by most command-line tools, since intercepting the exact
first body byte requires patching much deeper into http.client's internals.
"""

import http.client
import socket
import ssl
import time
from urllib.parse import urlsplit

USER_AGENT = "Vitalyze/2.0 (+https://github.com/)"


class TimedHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.timings = {"dns_ms": 0.0, "tcp_connect_ms": 0.0, "tls_handshake_ms": None}

        t0 = time.perf_counter()
        addr_info = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)
        t1 = time.perf_counter()
        self.timings["dns_ms"] = (t1 - t0) * 1000

        family, socktype, proto, _, sockaddr = addr_info[0]
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(self.timeout)

        t2 = time.perf_counter()
        sock.connect(sockaddr)
        t3 = time.perf_counter()
        self.timings["tcp_connect_ms"] = (t3 - t2) * 1000

        self.sock = sock


class TimedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        self.timings = {"dns_ms": 0.0, "tcp_connect_ms": 0.0, "tls_handshake_ms": 0.0}

        t0 = time.perf_counter()
        addr_info = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)
        t1 = time.perf_counter()
        self.timings["dns_ms"] = (t1 - t0) * 1000

        family, socktype, proto, _, sockaddr = addr_info[0]
        raw_sock = socket.socket(family, socktype, proto)
        raw_sock.settimeout(self.timeout)

        t2 = time.perf_counter()
        raw_sock.connect(sockaddr)
        t3 = time.perf_counter()
        self.timings["tcp_connect_ms"] = (t3 - t2) * 1000

        context = self._context or ssl.create_default_context()
        t4 = time.perf_counter()
        self.sock = context.wrap_socket(raw_sock, server_hostname=self.host)
        t5 = time.perf_counter()
        self.timings["tls_handshake_ms"] = (t5 - t4) * 1000


def single_request(url: str, timeout: int = 15, method: str = "GET") -> dict:
    """Perform one phase-timed request. Returns a flat dict; see module docstring."""
    parts = urlsplit(url)
    scheme = parts.scheme or "https"
    host = parts.hostname
    if not host:
        return {"success": False, "error": f"Could not parse host from URL: {url}"}

    port = parts.port or (443 if scheme == "https" else 80)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query

    conn_cls = TimedHTTPSConnection if scheme == "https" else TimedHTTPConnection
    conn = None
    result = {"success": False, "error": None}
    try:
        conn = conn_cls(host, port, timeout=timeout)
        t_start = time.perf_counter()
        conn.connect()

        conn.putrequest(method, path, skip_accept_encoding=False)
        conn.putheader("Host", host)
        conn.putheader("User-Agent", USER_AGENT)
        conn.putheader("Accept", "*/*")
        conn.putheader("Connection", "close")
        conn.endheaders()

        resp = conn.getresponse()
        t_ttfb = time.perf_counter()

        body = resp.read()
        t_done = time.perf_counter()

        total_ms = (t_done - t_start) * 1000
        ttfb_ms = (t_ttfb - t_start) * 1000
        download_ms = (t_done - t_ttfb) * 1000

        result.update({
            "success": True,
            "status_code": resp.status,
            "reason": resp.reason,
            "http_version": "HTTP/1.1" if resp.version == 11 else "HTTP/1.0",
            "content_length": len(body),
            "content_encoding": resp.getheader("Content-Encoding"),
            "response_headers": dict(resp.getheaders()),
            "dns_ms": round(conn.timings.get("dns_ms", 0.0), 2),
            "tcp_connect_ms": round(conn.timings.get("tcp_connect_ms", 0.0), 2),
            "tls_handshake_ms": (
                round(conn.timings["tls_handshake_ms"], 2)
                if conn.timings.get("tls_handshake_ms") is not None else None
            ),
            "ttfb_ms": round(ttfb_ms, 2),
            "download_ms": round(download_ms, 2),
            "total_ms": round(total_ms, 2),
        })
    except (socket.timeout, socket.gaierror, ConnectionRefusedError,
            ssl.SSLError, OSError, http.client.HTTPException) as e:
        result["error"] = str(e)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return result
