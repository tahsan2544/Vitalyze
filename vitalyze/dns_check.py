"""DNS resolution timing and record lookup."""

import socket
import time

from . import colors


def run(hostname: str) -> dict:
    hostname = hostname.split(":")[0]  # strip port if present
    result = {"hostname": hostname, "resolved": False, "addresses": [], "resolve_time_ms": None, "error": None}

    try:
        start = time.perf_counter()
        infos = socket.getaddrinfo(hostname, None)
        elapsed = (time.perf_counter() - start) * 1000

        addresses = sorted({info[4][0] for info in infos})
        result.update({
            "resolved": True,
            "addresses": addresses,
            "resolve_time_ms": round(elapsed, 2),
        })
    except socket.gaierror as e:
        result["error"] = str(e)

    return result


def print_result(result: dict) -> None:
    if not result["resolved"]:
        message = f"Failed to resolve {result['hostname']}: {result['error']}"
        print(f"    {colors.bad(message)}")
        return
    print(f"    {colors.ok('Resolved')}")
    print(f"    Host:          {result['hostname']}")
    print(f"    Addresses:     {', '.join(result['addresses'])}")
    print(f"    Resolve time:  {result['resolve_time_ms']} ms")
