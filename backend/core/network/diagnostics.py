"""Network diagnostic tools: ping, traceroute, DNS lookup, port scan, connectivity check."""
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def ping_host(host: str, count: int = 4, timeout: int = 5) -> Dict:
    """Ping 指定主机。"""
    host = host.strip()
    if not host or re.search(r'[;&|`$]', host):
        return {"success": False, "error": "Invalid host"}

    count = max(1, min(count, 20))
    timeout = max(1, min(timeout, 30))
    # Use -c for count, -W for deadline, -n for no DNS resolution
    out, code = run_cmd(
        f"ping -c {count} -W {timeout} -n {safe_quote(host)} 2>&1",
        timeout=timeout * count + 5
    )

    # Parse statistics
    stats = {"transmitted": 0, "received": 0, "loss": "100%", "min": "", "avg": "", "max": "", "mdev": ""}
    for line in out.splitlines():
        if "packets transmitted" in line:
            m = re.search(r'(\d+)\s+packets.*?(\d+)\s+received', line)
            if m:
                stats["transmitted"] = int(m.group(1))
                stats["received"] = int(m.group(2))
        if "loss" in line.lower() or "packet loss" in line:
            m = re.search(r'(\d+(?:\.\d+)?%)\s+(?:packet\s+)?loss', line)
            if m:
                stats["loss"] = m.group(1)
        if "min/avg/max" in line or "rtt min/avg/max" in line:
            parts = line.split("=")[-1].strip().split("/")
            if len(parts) >= 4:
                stats["min"] = parts[0].strip()
                stats["avg"] = parts[1].strip()
                stats["max"] = parts[2].strip()
                stats["mdev"] = parts[3].strip().split()[0]

    return {
        "success": code == 0,
        "host": host,
        "output": out.strip(),
        "stats": stats,
    }


def traceroute_host(host: str, max_hops: int = 30, timeout: int = 3) -> Dict:
    """Traceroute 到指定主机。"""
    host = host.strip()
    if not host or re.search(r'[;&|`$]', host):
        return {"success": False, "error": "Invalid host"}

    max_hops = max(5, min(max_hops, 64))
    timeout = max(1, min(timeout, 10))

    # Try traceroute first, then fallback to tracepath
    for cmd in [
        f"sudo traceroute -n -m {max_hops} -w {timeout} {safe_quote(host)} 2>&1",
        f"tracepath -n -m {max_hops} {safe_quote(host)} 2>&1",
    ]:
        out, code = run_cmd(cmd, timeout=max_hops * timeout + 10)
        if out.strip():
            break

    # Parse hops
    hops = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("traceroute") or line.startswith("tracepath"):
            continue
        # Format: " 1  192.168.1.1  0.123 ms  0.456 ms  0.789 ms"
        m = re.match(r'\s*(\d+)\s+(.+)', line)
        if m:
            hop_num = int(m.group(1))
            hop_data = m.group(2)
            # Extract IP addresses and times
            ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', hop_data)
            times = re.findall(r'(\d+\.\d+)\s*ms', hop_data)
            asterisks = hop_data.count('*')
            hops.append({
                "hop": hop_num,
                "ips": ips,
                "times": [f"{t} ms" for t in times],
                "timeouts": asterisks,
            })

    return {
        "success": code == 0,
        "host": host,
        "output": out.strip(),
        "hops": hops,
    }


def dns_lookup(domain: str, record_type: str = "A") -> Dict:
    """DNS 查询。"""
    domain = domain.strip()
    if not domain or re.search(r'[;&|`$]', domain):
        return {"success": False, "error": "Invalid domain"}

    allowed_types = {"A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR", "SRV"}
    if record_type not in allowed_types:
        return {"success": False, "error": f"Unsupported record type: {record_type}"}

    # Try dig first, then nslookup, then host
    out, code = run_cmd(f"dig +short {safe_quote(domain)} {safe_quote(record_type)} 2>&1", timeout=10)
    records = [r.strip() for r in out.splitlines() if r.strip()]

    if not records:
        out2, _ = run_cmd(f"host -t {safe_quote(record_type)} {safe_quote(domain)} 2>&1", timeout=10)
        for line in out2.splitlines():
            if "has address" in line or "mail is handled" in line or "descriptive text" in line:
                records.append(line.strip())
            elif "not found" in line.lower():
                pass
            elif line.strip() and not line.startswith("Using") and not line.startswith("Host"):
                records.append(line.strip())

    return {
        "success": True,
        "domain": domain,
        "type": record_type,
        "records": records,
    }


def port_scan(host: str, ports: str = "22,80,443,3306,5432,6379,8080,8443") -> Dict:
    """端口扫描（使用 nc 或 /dev/tcp）。"""
    host = host.strip()
    if not host or re.search(r'[;&|`$]', host):
        return {"success": False, "error": "Invalid host"}

    port_list = []
    for p in ports.split(","):
        p = p.strip()
        if p.isdigit() and 1 <= int(p) <= 65535:
            port_list.append(p)

    if not port_list:
        return {"success": False, "error": "No valid ports specified"}

    results = []
    for port in port_list:
        out, code = run_cmd(
            f"timeout 2 bash -c 'echo >/dev/tcp/{safe_quote(host)}/{port}' 2>&1",
            timeout=3
        )
        results.append({
            "port": int(port),
            "open": code == 0,
            "service": _guess_service(port),
        })

    return {
        "success": True,
        "host": host,
        "results": results,
        "open_count": sum(1 for r in results if r["open"]),
    }


def _guess_service(port: str) -> str:
    """根据端口号猜测服务名。"""
    common = {
        "21": "ftp", "22": "ssh", "23": "telnet", "25": "smtp",
        "53": "dns", "80": "http", "110": "pop3", "143": "imap",
        "443": "https", "993": "imaps", "995": "pop3s",
        "3306": "mysql", "5432": "postgresql", "6379": "redis",
        "27017": "mongodb", "8080": "http-alt", "8443": "https-alt",
        "9090": "cockpit", "3000": "grafana", "9200": "elasticsearch",
    }
    return common.get(port, "unknown")


def check_connectivity(target: str = "8.8.8.8") -> Dict:
    """检查网络连通性。"""
    result = {
        "ipv4": False,
        "ipv6": False,
        "dns": False,
        "gateway": False,
        "internet": False,
    }

    # Check default gateway
    gw_out, _ = run_cmd("ip route show default 2>/dev/null | awk '{print $3}' | head -1")
    gw = gw_out.strip()
    result["gateway"] = bool(gw)
    if gw:
        _, code = run_cmd(f"ping -c 1 -W 2 {safe_quote(gw)} 2>/dev/null")
        result["gateway"] = code == 0

    # Check DNS
    dns_out, _ = run_cmd("dig +short +timeout=2 google.com 2>/dev/null || nslookup google.com 2>/dev/null | grep -c 'Address'")
    result["dns"] = bool(dns_out.strip() and "server can't" not in dns_out.lower())

    # Check internet connectivity
    _, code = run_cmd(f"ping -c 1 -W 2 {safe_quote(target)} 2>/dev/null")
    result["internet"] = code == 0
    result["ipv4"] = result["internet"]

    # Check IPv6
    _, code = run_cmd("ping6 -c 1 -W 2 2001:4860:4860::8888 2>/dev/null")
    result["ipv6"] = code == 0

    return result
