import time
from backend.collector import (
    SystemMetricsCollector,
    parse_proc_net_tables,
    parse_psi_file,
    parse_ufw_rules,
)

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
    assert "ufw" in s1["network"]

    # Sleep slightly and collect second snapshot to verify delta calculations
    time.sleep(0.05)
    s2 = collector.collect_snapshot()
    assert s2["timestamp"] > s1["timestamp"]
    assert s2["disk"]["read_mbs"] >= 0.0
    assert s2["network"]["rx_kbs"] >= 0.0


def test_parse_proc_net_tables(tmp_path):
    net_dir = tmp_path / "1" / "net"
    net_dir.mkdir(parents=True)
    header = (
        "  sl  local_address rem_address   st tx_queue rx_queue "
        "tr tm->when retrnsmt   uid  timeout inode\n"
    )
    (net_dir / "tcp").write_text(
        header
        + "   0: 0100007F:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 111 1 0\n"
        + "   1: 0100007F:1F90 0100007F:C350 01 00000000:00000000 00:00000000 00000000     0        0 222 1 0\n"
    )
    (net_dir / "tcp6").write_text(
        header
        + "   0: 00000000000000000000000001000000:01BB 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 333 1 0\n"
    )
    (net_dir / "udp").write_text(
        header
        + "   0: 00000000:0035 00000000:0000 07 00000000:00000000 00:00000000 00000000     0        0 444 1 0\n"
    )
    (net_dir / "udp6").write_text(header)

    ports, counts = parse_proc_net_tables(str(tmp_path))

    assert {(p["port"], p["address"], p["proto"]) for p in ports} == {
        (22, "127.0.0.1", "tcp"),
        (443, "::1", "tcp"),
        (53, "0.0.0.0", "udp"),
    }
    assert counts["LISTEN"] == 2
    assert counts["ESTABLISHED"] == 1
    assert counts["OTHER"] == 1


def test_parse_proc_net_tables_missing(tmp_path):
    assert parse_proc_net_tables(str(tmp_path)) is None


def test_parse_ufw_rules(tmp_path):
    (tmp_path / "ufw.conf").write_text("ENABLED=yes\n")
    (tmp_path / "user.rules").write_text(
        "*filter\n"
        "### tuple ### allow tcp 22 0.0.0.0/0 any 0.0.0.0/0 in\n"
        "-A ufw-user-input -p tcp --dport 22 -j ACCEPT\n"
        "### tuple ### limit tcp 2222 0.0.0.0/0 any 0.0.0.0/0 in\n"
        "### tuple ### deny tcp 3306 0.0.0.0/0 any 0.0.0.0/0 in\n"
    )
    (tmp_path / "user6.rules").write_text(
        "### tuple ### allow tcp 443 ::/0 any ::/0 in\n"
    )

    result = parse_ufw_rules(str(tmp_path))

    assert result["available"] is True
    assert result["enabled"] is True
    assert [(r["action"], r["port"]) for r in result["rules"]] == [
        ("allow", "22"),
        ("allow", "443"),
        ("limit", "2222"),
    ]


def test_parse_ufw_rules_unavailable(tmp_path):
    assert parse_ufw_rules(str(tmp_path)) == {
        "available": False,
        "enabled": False,
        "rules": [],
    }
