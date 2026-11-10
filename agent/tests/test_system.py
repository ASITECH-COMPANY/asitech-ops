import pytest

from asitech_agent import system

STAT = """cpu  100 0 50 800 50 0 0 0 0 0
cpu0 50 0 25 400 25 0 0 0 0 0
intr 1 2 3
"""

MEMINFO = """MemTotal:        8000000 kB
MemFree:          500000 kB
MemAvailable:    6000000 kB
Buffers:          100000 kB
"""

NET_DEV = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 999999     100    0    0    0     0          0         0   999999     100    0    0    0     0       0          0
  eth0: 1000       10    0    0    0     0          0         0     2000      20    0    0    0     0       0          0
docker0: 300        3    0    0    0     0          0         0      400       4    0    0    0     0       0          0
"""


def test_cpu_times():
    busy, total = system.parse_cpu_times(STAT)
    assert total == 1000
    assert busy == 150


def test_cpu_times_requires_aggregate_line():
    with pytest.raises(ValueError):
        system.parse_cpu_times("cpu0 1 2 3 4\n")


def test_meminfo_uses_available_memory():
    used, total = system.parse_meminfo(MEMINFO)
    assert total == 8_000_000 * 1024
    assert used == 2_000_000 * 1024


def test_net_dev_excludes_loopback():
    assert system.parse_net_dev(NET_DEV) == (1300, 2400)


def test_os_release():
    values = system.parse_os_release('NAME="Ubuntu"\nVERSION_ID="24.04"\n# comment\nID=ubuntu\n')
    assert values == {"NAME": "Ubuntu", "VERSION_ID": "24.04", "ID": "ubuntu"}


def test_collector_on_this_machine():
    """Smoke test against the real /proc of the test runner (Linux)."""
    collector = system.MetricsCollector()
    metrics = collector.collect()
    assert 0 <= metrics["cpu_percent"] <= 100
    assert 0 < metrics["memory_used"] <= metrics["memory_total"]
    assert 0 < metrics["disk_used"] <= metrics["disk_total"]
    facts = system.collect_facts()
    assert facts["cpu_count"] >= 1
    assert facts["agent_version"]


def test_docker_version_handles_missing_socket(tmp_path):
    assert system.docker_version(str(tmp_path / "missing.sock")) is None
