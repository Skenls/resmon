import time
from backend.collector import SystemMetricsCollector, parse_psi_file

def test_parse_psi_content():
    content = """some avg10=0.04 avg60=0.02 avg300=0.01 total=1234567
full avg10=0.00 avg60=0.00 avg300=0.00 total=0"""
    parsed = parse_psi_file(content)
    assert "some" in parsed
    assert parsed["some"]["avg10"] == 0.04
    assert parsed["some"]["avg60"] == 0.02
    assert parsed["some"]["avg300"] == 0.01
    assert parsed["some"]["total"] == 1234567
    assert "full" in parsed
    assert parsed["full"]["avg10"] == 0.00

def test_parse_psi_empty():
    assert parse_psi_file("") == {}
    assert parse_psi_file(None) == {}

def test_collector_static_info():
    collector = SystemMetricsCollector()
    info = collector.get_static_info()
    assert "hostname" in info
    assert "os" in info
    assert "kernel" in info
    assert "cpu_cores_logical" in info
    assert "total_memory" in info
    assert "boot_time" in info
    assert "uptime_seconds" in info

def test_collector_snapshot_structure():
    collector = SystemMetricsCollector()
    # First snapshot
    s1 = collector.collect_snapshot()
    assert "timestamp" in s1
    assert "cpu" in s1
    assert "overall" in s1["cpu"]
    assert "cores" in s1["cpu"]
    assert isinstance(s1["cpu"]["cores"], list)
    assert "loadavg" in s1["cpu"]
    assert "psi_some" in s1["cpu"]

    assert "memory" in s1
    assert "total" in s1["memory"]
    assert "used" in s1["memory"]
    assert "percent" in s1["memory"]
    assert "swap_total" in s1["memory"]
    assert "page_faults_minor_sec" in s1["memory"]

    assert "disk" in s1
    assert "read_mbs" in s1["disk"]
    assert "write_mbs" in s1["disk"]
    assert "read_iops" in s1["disk"]
    assert "write_iops" in s1["disk"]
    assert "partitions" in s1["disk"]

    assert "network" in s1
    assert "rx_kbs" in s1["network"]
    assert "tx_kbs" in s1["network"]
    assert "connections_count" in s1["network"]
    assert "listening_ports" in s1["network"]

    # Sleep slightly and collect second snapshot to verify delta calculations
    time.sleep(0.05)
    s2 = collector.collect_snapshot()
    assert s2["timestamp"] > s1["timestamp"]
    assert s2["disk"]["read_mbs"] >= 0.0
    assert s2["network"]["rx_kbs"] >= 0.0
