"""System facts and metrics, read directly from Linux (/proc, statvfs, Docker socket).

No third-party dependency: the parsing functions take file contents so they can
be tested with fixtures.
"""

from __future__ import annotations

import http.client
import json
import os
import platform
import socket
import time
from pathlib import Path

from . import __version__

PROC = Path(os.environ.get("ASITECH_AGENT_PROC", "/proc"))
DOCKER_SOCKET = os.environ.get("ASITECH_AGENT_DOCKER_SOCKET", "/var/run/docker.sock")
DISK_PATH = os.environ.get("ASITECH_AGENT_DISK_PATH", "/")


def _read(name: str) -> str:
    return (PROC / name).read_text()


# --- Parsers --------------------------------------------------------------------------------


def parse_cpu_times(stat: str) -> tuple[int, int]:
    """Return (busy, total) jiffies from the aggregate "cpu" line of /proc/stat."""
    for line in stat.splitlines():
        if line.startswith("cpu "):
            values = [int(v) for v in line.split()[1:9]]
            values += [0] * (8 - len(values))
            user, nice, system, idle, iowait, irq, softirq, steal = values
            idle_all = idle + iowait
            total = user + nice + system + irq + softirq + steal + idle_all
            return total - idle_all, total
    raise ValueError("no aggregate cpu line in /proc/stat")


def parse_meminfo(meminfo: str) -> tuple[int, int]:
    """Return (used, total) bytes. "Used" excludes reclaimable cache (MemAvailable)."""
    values: dict[str, int] = {}
    for line in meminfo.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts:
            values[key] = int(parts[0]) * (1024 if len(parts) > 1 and parts[1] == "kB" else 1)
    total = values["MemTotal"]
    available = values.get("MemAvailable", values.get("MemFree", 0))
    return max(0, total - available), total


def parse_net_dev(net_dev: str) -> tuple[int, int]:
    """Return cumulative (rx, tx) bytes over all interfaces except loopback."""
    rx = tx = 0
    for line in net_dev.splitlines()[2:]:
        name, _, data = line.partition(":")
        if name.strip() == "lo" or not data:
            continue
        fields = data.split()
        rx += int(fields[0])
        tx += int(fields[8])
    return rx, tx


def parse_os_release(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


# --- Collection --------------------------------------------------------------------------------


def disk_usage(path: str = DISK_PATH) -> tuple[int, int]:
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    return used, total


def docker_version(socket_path: str = DOCKER_SOCKET, timeout: float = 3.0) -> str | None:
    """Docker Engine version over the local socket (read-only call), or None."""

    class UnixHTTPConnection(http.client.HTTPConnection):
        def connect(self) -> None:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(socket_path)
            self.sock = sock

    try:
        connection = UnixHTTPConnection("localhost", timeout=timeout)
        connection.request("GET", "/version")
        response = connection.getresponse()
        if response.status != 200:
            return None
        version = json.loads(response.read(65536)).get("Version")
        return str(version)[:50] if version else None
    except (OSError, ValueError, http.client.HTTPException):
        return None


def collect_facts() -> dict:
    try:
        os_release = parse_os_release(Path("/etc/os-release").read_text())
    except OSError:
        os_release = {}
    _, memory_total = parse_meminfo(_read("meminfo"))
    _, disk_total = disk_usage()
    facts = {
        "hostname": socket.gethostname(),
        "os_name": os_release.get("NAME", platform.system()),
        "os_version": os_release.get("VERSION_ID", ""),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "memory_total": memory_total,
        "disk_total": disk_total,
        "agent_version": __version__,
    }
    version = docker_version()
    if version:
        facts["docker_version"] = version
    return {k: v for k, v in facts.items() if v not in ("", None)}


class MetricsCollector:
    """CPU usage is a rate: it is computed between two successive collections."""

    def __init__(self) -> None:
        self._previous = parse_cpu_times(_read("stat"))
        self._previous_at = time.monotonic()

    def _cpu_percent(self) -> float:
        busy, total = parse_cpu_times(_read("stat"))
        prev_busy, prev_total = self._previous
        self._previous = (busy, total)
        delta_total = total - prev_total
        if delta_total <= 0:
            return 0.0
        return round(min(100.0, max(0.0, 100.0 * (busy - prev_busy) / delta_total)), 2)

    def collect(self) -> dict:
        if time.monotonic() - self._previous_at < 0.2:
            time.sleep(0.25)  # first call: give the CPU counters time to move
        self._previous_at = time.monotonic()
        memory_used, memory_total = parse_meminfo(_read("meminfo"))
        disk_used, disk_total = disk_usage()
        rx, tx = parse_net_dev(_read("net/dev"))
        return {
            "cpu_percent": self._cpu_percent(),
            "load1": round(os.getloadavg()[0], 2),
            "memory_used": memory_used,
            "memory_total": memory_total,
            "disk_used": disk_used,
            "disk_total": disk_total,
            "net_rx_bytes": rx,
            "net_tx_bytes": tx,
            "uptime_seconds": int(float(_read("uptime").split()[0])),
        }
