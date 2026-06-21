"""Interface detection, DNS, and IP configuration (static/DHCP)."""
import os
import re
import tempfile
import time
import ipaddress
import psutil
import json
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def _validate_dns_server(s: str) -> bool:
    """Validate IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def get_network_interfaces() -> List[Dict]:
    """获取所有网络接口信息（iproute2 JSON + psutil 回退，全发行版兼容）。"""
    # 首选: ip -j（iproute2 自带，所有现代 Linux 发行版都有）
    out, code = run_cmd("ip -j addr show 2>/dev/null")
    if code == 0 and out.strip():
        try:
            data = json.loads(out)
            interfaces = []
            for iface in data:
                info = {
                    "name": iface.get("ifname", ""),
                    "ipv4": [],
                    "ipv6": [],
                    "mac": iface.get("address", ""),
                    "is_up": "UP" in iface.get("flags", []),
                    "speed": iface.get("speed", 0),
                    "mtu": iface.get("mtu", 0),
                    "operstate": iface.get("operstate", "unknown"),
                }
                for addr in iface.get("addr_info", []):
                    if addr.get("family") == "inet":
                        info["ipv4"].append(addr.get("local", ""))
                    elif addr.get("family") == "inet6":
                        info["ipv6"].append(addr.get("local", ""))
                interfaces.append(info)
            return interfaces
        except (json.JSONDecodeError, KeyError):
            pass

    # 回退: psutil
    try:
        interfaces = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for name, addr_list in addrs.items():
            info: Dict = {"name": name, "ipv4": [], "ipv6": [], "mac": "", "is_up": False, "speed": 0, "mtu": 0}
            for addr in addr_list:
                family = str(addr.family)
                if "AF_INET" in family and "AF_INET6" not in family:
                    info["ipv4"].append(addr.address)
                elif "AF_INET6" in family:
                    info["ipv6"].append(addr.address)
                elif "AF_LINK" in family or "AF_PACKET" in family:
                    info["mac"] = addr.address
            if name in stats:
                info["is_up"] = stats[name].isup
                info["speed"] = stats[name].speed
                info["mtu"] = stats[name].mtu
            interfaces.append(info)
        return interfaces
    except Exception:
        pass

    return []


def get_dns() -> List[str]:
    """Get current DNS servers. Checks systemd-resolved, resolvconf, then /etc/resolv.conf."""
    dns: List[str] = []

    # 1. systemd-resolved via resolvectl
    _, code = run_cmd("which resolvectl 2>/dev/null")
    if code == 0:
        out, _ = run_cmd("resolvectl dns 2>/dev/null")
        for line in out.splitlines():
            # Lines like "Link 2 (eth0): 1.2.3.4 5.6.7.8"
            if ":" in line:
                addr_part = line.split(":", 1)[1].strip()
                for token in addr_part.split():
                    if _validate_dns_server(token):
                        if token not in dns:
                            dns.append(token)
        if dns:
            return dns

        # Fallback: parse /etc/systemd/resolved.conf
        try:
            with open("/etc/systemd/resolved.conf") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DNS="):
                        servers = line.split("=", 1)[1].strip()
                        for s in servers.split():
                            s = s.strip()
                            if _validate_dns_server(s) and s not in dns:
                                dns.append(s)
        except Exception:
            pass
        if dns:
            return dns

    # 2. resolvconf: check /run/resolvconf/ and /etc/resolvconf/
    for rdir in ("/run/resolvconf/interface", "/etc/resolvconf/run/interface"):
        if os.path.isdir(rdir):
            try:
                for fname in os.listdir(rdir):
                    fpath = os.path.join(rdir, fname)
                    try:
                        with open(fpath) as f:
                            for line in f:
                                if line.startswith("nameserver"):
                                    s = line.split()[1]
                                    if _validate_dns_server(s) and s not in dns:
                                        dns.append(s)
                    except Exception:
                        pass
            except Exception:
                pass
        if dns:
            return dns

    # 3. Direct /etc/resolv.conf
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    ns = line.strip().split()[1]
                    if _validate_dns_server(ns) and ns not in dns:
                        dns.append(ns)
    except Exception:
        pass

    return dns


def _detect_dns_method() -> str:
    """Detect the active DNS management method.

    Returns:
        "systemd-resolved" – systemd-resolved is active
        "resolvconf"        – resolvconf package is present
        "direct"            – fallback to writing /etc/resolv.conf directly
    """
    # Check systemd-resolved
    _, code = run_cmd("systemctl is-active systemd-resolved 2>/dev/null")
    if code == 0:
        return "systemd-resolved"

    # Also check resolvectl as fallback for systemd-resolved
    _, code = run_cmd("which resolvectl 2>/dev/null")
    if code == 0:
        out, _ = run_cmd("resolvectl status 2>/dev/null | head -5")
        if "resolved" in out.lower() or "DNS" in out:
            return "systemd-resolved"

    # Check resolvconf
    _, code = run_cmd("which resolvconf 2>/dev/null")
    if code == 0:
        return "resolvconf"

    return "direct"


def set_dns(servers: List[str]) -> Dict:
    """Update DNS servers. Auto-detects systemd-resolved / resolvconf / direct.

    For systemd-resolved: uses resolvectl dns on each real interface.
    For resolvconf: pipes nameserver lines through sudo resolvconf -a.
    For direct: writes /etc/resolv.conf as a last resort.
    """
    if not servers:
        return {"success": False, "message": "At least one DNS server is required"}
    for s in servers:
        if not _validate_dns_server(s):
            return {"success": False, "message": f"Invalid DNS server: {s}"}

    method = _detect_dns_method()

    # ── 1. systemd-resolved ──
    if method == "systemd-resolved":
        dns_list = " ".join(safe_quote(s) for s in servers)
        ok_any = False
        messages = []

        # Per-interface: apply on every non-loopback, up, real interface
        iface_out, _ = run_cmd("ip -j link show up 2>/dev/null")
        try:
            links = json.loads(iface_out)
            for link in links:
                ifname = link.get("ifname", "")
                if ifname == "lo":
                    continue
                out, code = run_cmd(
                    f"sudo resolvectl dns {safe_quote(ifname)} {dns_list} 2>&1",
                    timeout=10
                )
                if code == 0:
                    ok_any = True
                    messages.append(f"{ifname}: OK")
                else:
                    messages.append(f"{ifname}: {out.strip()}")
        except (json.JSONDecodeError, KeyError):
            pass

        # Also set global DNS fallback
        out, code = run_cmd(
            f"sudo resolvectl dns global {dns_list} 2>&1",
            timeout=10
        )
        if code == 0:
            ok_any = True

        if ok_any:
            return {"success": True, "message": "DNS updated via systemd-resolved: " + "; ".join(messages)}
        else:
            return {"success": False, "message": "Failed via systemd-resolved: " + "; ".join(messages)}

    # ── 2. resolvconf ──
    if method == "resolvconf":
        # Get the default-route interface as the best per-interface name
        iface_out, _ = run_cmd("ip route show default 2>/dev/null | awk '{print $5}' | head -1")
        iface = iface_out.strip()
        if not iface:
            iface = "eth0"

        input_lines = "\n".join(f"nameserver {s}" for s in servers)

        # Use sudo sh -c to pipe through resolvconf as a privileged command
        out, code = run_cmd(
            f"printf '%s\\n' {safe_quote(input_lines)} | sudo resolvconf -a {safe_quote(iface)}.inet 2>&1",
            timeout=10
        )
        if code == 0:
            return {"success": True, "message": f"DNS updated via resolvconf on {iface}.inet"}
        else:
            # Fallback: try without .inet suffix (older resolvconf versions)
            out2, code2 = run_cmd(
                f"printf '%s\\n' {safe_quote(input_lines)} | sudo resolvconf -a {safe_quote(iface)} 2>&1",
                timeout=10
            )
            if code2 == 0:
                return {"success": True, "message": f"DNS updated via resolvconf on {iface}"}
            return {"success": False, "message": f"resolvconf failed: {out.strip()}"}

    # ── 3. Direct /etc/resolv.conf (last resort) ──
    content = "# Generated by TuxTackleBox\n"
    for s in servers:
        content += f"nameserver {s}\n"
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".resolv", delete=False)
    try:
        tmp.write(content)
        tmp.close()
        _, code = run_cmd(
            f"sudo chattr -i /etc/resolv.conf 2>/dev/null; "
            f"sudo cp {safe_quote(tmp.name)} /etc/resolv.conf"
        )
        return {"success": code == 0, "message": "DNS updated via /etc/resolv.conf" if code == 0
                else "Failed to update DNS"}
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


# ── 网络管理系统检测 ──

def detect_network_manager() -> str:
    """检测系统使用的网络管理方案：netplan / NetworkManager / ifcfg / none。"""
    # 检查 netplan
    if os.path.exists("/etc/netplan/") and os.listdir("/etc/netplan/"):
        _, code = run_cmd("which netplan 2>/dev/null")
        if code == 0:
            return "netplan"
    # 检查 NetworkManager
    _, code = run_cmd("which nmcli 2>/dev/null")
    if code == 0:
        nm_out, _ = run_cmd("nmcli -t -f RUNNING general status 2>/dev/null")
        if "running" in nm_out.lower():
            return "NetworkManager"
    # 检查传统 ifcfg (RHEL)
    if os.path.exists("/etc/sysconfig/network-scripts/"):
        return "ifcfg"
    return "none"


def _detect_netplan_renderer() -> str:
    """Detect the correct netplan renderer: NetworkManager or networkd.

    Checks:
      1. systemctl is-active NetworkManager
      2. nmcli -t -f RUNNING general status (fallback)
      3. Defaults to networkd for headless/server systems.
    """
    # Check if NetworkManager service is active via systemd
    _, code = run_cmd("systemctl is-active NetworkManager 2>/dev/null")
    if code == 0:
        return "NetworkManager"

    # Fallback: nmcli status check
    _, code = run_cmd("which nmcli 2>/dev/null")
    if code == 0:
        nm_out, _ = run_cmd("nmcli -t -f RUNNING general status 2>/dev/null")
        if nm_out.strip().lower() == "running":
            return "NetworkManager"

    # Default: systemd-networkd (common on server/headless)
    return "networkd"


def _write_ifcfg(iface: str, ip_config: Dict) -> Tuple[str, int]:
    """Write RHEL-style ifcfg file to /etc/sysconfig/network-scripts/ifcfg-{iface}.

    Supports both static and DHCP configuration.  BOOTPROTO, IPADDR, NETMASK,
    GATEWAY, and DNS1 are set for static; only BOOTPROTO=dhcp for DHCP.

    After writing the file the interface is brought up via ifup (SysV) or
    nmcli conn reload / nmcli dev reapply (NetworkManager controlled ifcfg).
    """
    path = f"/etc/sysconfig/network-scripts/ifcfg-{iface}"
    lines = [
        f"DEVICE={iface}",
        "ONBOOT=yes",
    ]
    if ip_config.get("dhcp"):
        lines.append("BOOTPROTO=dhcp")
    else:
        lines.append("BOOTPROTO=static")
        if ip_config.get("address"):
            lines.append(f"IPADDR={ip_config['address']}")
        if ip_config.get("netmask"):
            lines.append(f"NETMASK={ip_config['netmask']}")
        if ip_config.get("gateway"):
            lines.append(f"GATEWAY={ip_config['gateway']}")
        if ip_config.get("dns"):
            lines.append(f"DNS1={ip_config['dns']}")
    content = "\n".join(lines) + "\n"
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".ifcfg", delete=False)
    try:
        tmp.write(content)
        tmp.close()
        # Try ifup first (traditional SysV); fall back to nmcli for NM-managed ifcfg
        out, code = run_cmd(
            f"sudo cp {safe_quote(tmp.name)} {path} && "
            f"(sudo ifup {safe_quote(iface)} 2>&1 || "
            f"sudo nmcli conn reload 2>/dev/null && sudo nmcli conn up {safe_quote(iface)} 2>/dev/null || "
            f"sudo nmcli dev reapply {safe_quote(iface)} 2>/dev/null || true)",
            timeout=20
        )
        return out.strip(), code
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def get_interface_ip_mode(iface: str) -> str:
    """检测接口的 IP 获取方式：dhcp / static / manual / loopback。"""
    if iface == "lo":
        return "loopback"

    # NetworkManager 方式
    _, code = run_cmd("which nmcli 2>/dev/null")
    if code == 0:
        out, _ = run_cmd(f"nmcli -t -f IP4.METHOD con show {safe_quote(iface)} 2>/dev/null")
        if out.strip():
            method = out.strip().lower()
            if "auto" in method or "dhcp" in method:
                return "dhcp"
            elif "manual" in method:
                return "static"

    # netplan 方式
    if os.path.exists("/etc/netplan/"):
        for f in os.listdir("/etc/netplan/"):
            if f.endswith(".yaml") or f.endswith(".yml"):
                try:
                    with open(os.path.join("/etc/netplan/", f)) as fp:
                        content = fp.read()
                        if iface in content:
                            if "dhcp4: true" in content or "dhcp4: yes" in content:
                                return "dhcp"
                            elif "addresses:" in content:
                                return "static"
                except Exception:
                    pass

    # 检查实际是否有 IP（有 IP 但没有 dhclient 进程 → 静态）
    ip_out, _ = run_cmd(f"ip -j addr show {safe_quote(iface)} 2>/dev/null")
    try:
        data = json.loads(ip_out)
        if data and data[0].get("addr_info"):
            has_ip = any(a.get("family") == "inet" and "dynamic" not in a for a in data[0]["addr_info"])
            has_dhcp = any(a.get("family") == "inet" and a.get("dynamic", False) for a in data[0]["addr_info"])
            if has_dhcp:
                return "dhcp"
            if has_ip:
                return "static"
    except (json.JSONDecodeError, IndexError, KeyError):
        pass

    return "dhcp"  # default assumption


# ── IP 地址管理 (netplan + NetworkManager) ──

def get_ip_config(interface: str) -> Dict:
    """获取指定接口的 IP 配置 (mode, netmask, gateway, dns)。"""
    result: Dict = {"mode": "dhcp", "netmask": "24", "gateway": "", "dns": ""}

    # Get IP mode and netmask
    out, _ = run_cmd(f"ip -j addr show {safe_quote(interface)} 2>/dev/null")
    try:
        data = json.loads(out)
        if data and data[0].get("addr_info"):
            for addr in data[0]["addr_info"]:
                if addr.get("family") == "inet":
                    result["mode"] = "static"
                    result["netmask"] = str(addr.get("prefixlen", 24))
    except (json.JSONDecodeError, IndexError):
        pass

    # Get gateway
    rt_out, _ = run_cmd(f"ip route show default dev {safe_quote(interface)} 2>/dev/null | head -1")
    if rt_out:
        parts = rt_out.split()
        if "via" in parts:
            idx = parts.index("via")
            if idx + 1 < len(parts):
                result["gateway"] = parts[idx + 1]

    # Get DNS from resolv.conf
    dns_out, _ = run_cmd("grep -E '^nameserver' /etc/resolv.conf 2>/dev/null | head -1")
    if dns_out:
        dns_parts = dns_out.split()
        if len(dns_parts) > 1:
            result["dns"] = dns_parts[1]

    return result


def set_static_ip(interface: str, address: str, netmask: str = "24",
                  gateway: str = "", dns: str = "") -> Tuple[str, int]:
    """设置静态 IP。自动适配 NetworkManager / netplan。"""
    nm = detect_network_manager()
    cidr = f"{address}/{netmask}"

    if nm == "NetworkManager":
        con_name = _get_nm_connection(interface) or interface
        cmds = [
            f"sudo nmcli con mod {safe_quote(con_name)} ipv4.addresses {safe_quote(cidr)}",
            f"sudo nmcli con mod {safe_quote(con_name)} ipv4.method manual",
        ]
        if gateway:
            cmds.append(f"sudo nmcli con mod {safe_quote(con_name)} ipv4.gateway {safe_quote(gateway)}")
        if dns:
            cmds.append(f"sudo nmcli con mod {safe_quote(con_name)} ipv4.dns {safe_quote(dns)}")
        cmds.append(f"sudo nmcli con up {safe_quote(con_name)} 2>/dev/null || sudo nmcli dev reapply {safe_quote(interface)} 2>/dev/null")
        return run_cmd(" && ".join(cmds), timeout=20)

    elif nm == "netplan":
        renderer = _detect_netplan_renderer()
        # Validate interface name for filesystem-safe use (netplan names are
        # limited to [a-zA-Z0-9._-]; reject anything with shell metacharacters)
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', interface):
            return f"Invalid interface name for netplan: {interface}", -1

        target = f"/etc/netplan/60-{interface}.yaml"
        if os.path.exists(target):
            backup = f"{target}.bak-{int(time.time())}"
            run_cmd(f"sudo cp {safe_quote(target)} {safe_quote(backup)} 2>/dev/null", timeout=5)

        # 写入 netplan YAML
        yaml_content = f"""network:
  version: 2
  renderer: {renderer}
  ethernets:
    {interface}:
      dhcp4: false
      addresses: [{cidr}]
"""
        if gateway:
            yaml_content += f"      routes:\n        - to: default\n          via: {gateway}\n"
        if dns:
            yaml_content += f"      nameservers:\n        addresses: [{dns}]\n"

        tmp_path = f"/tmp/netplan-{interface}.yaml"
        try:
            with open(tmp_path, 'w') as f:
                f.write(yaml_content)
            out, code = run_cmd(
                f"sudo cp {safe_quote(tmp_path)} {safe_quote(target)} && "
                f"sudo netplan apply 2>&1",
                timeout=20
            )
            os.remove(tmp_path)
            return out.strip(), code
        except Exception as e:
            return str(e), -1

    # fallback: ip 命令

    elif nm == "ifcfg":
        return _write_ifcfg(interface, {"address": address, "netmask": netmask, "gateway": gateway, "dns": dns})

    out, code = run_cmd(
        f"sudo ip addr add {safe_quote(cidr)} dev {safe_quote(interface)} 2>&1 || "
        f"sudo ip addr replace {safe_quote(cidr)} dev {safe_quote(interface)} 2>&1",
        timeout=10
    )
    if code == 0 and gateway:
        run_cmd(f"sudo ip route add default via {safe_quote(gateway)} dev {safe_quote(interface)} 2>/dev/null", timeout=10)
    return out.strip(), code


def set_dhcp(interface: str) -> Tuple[str, int]:
    """启用 DHCP。自动适配 NetworkManager / netplan。"""
    nm = detect_network_manager()

    if nm == "NetworkManager":
        con_name = _get_nm_connection(interface) or interface
        return run_cmd(
            f"sudo nmcli con mod {safe_quote(con_name)} ipv4.method auto && "
            f"sudo nmcli con up {safe_quote(con_name)} 2>/dev/null || "
            f"sudo nmcli dev reapply {safe_quote(interface)} 2>/dev/null",
            timeout=20
        )

    elif nm == "netplan":
        renderer = _detect_netplan_renderer()
        # Validate interface name for filesystem-safe use
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', interface):
            return f"Invalid interface name for netplan: {interface}", -1

        target = f"/etc/netplan/60-{interface}.yaml"
        if os.path.exists(target):
            backup = f"{target}.bak-{int(time.time())}"
            run_cmd(f"sudo cp {safe_quote(target)} {safe_quote(backup)} 2>/dev/null", timeout=5)

        yaml_content = f"""network:
  version: 2
  renderer: {renderer}
  ethernets:
    {interface}:
      dhcp4: true
"""
        tmp_path = f"/tmp/netplan-{interface}.yaml"
        try:
            with open(tmp_path, 'w') as f:
                f.write(yaml_content)
            out, code = run_cmd(
                f"sudo cp {safe_quote(tmp_path)} {safe_quote(target)} && "
                f"sudo netplan apply 2>&1",
                timeout=20
            )
            os.remove(tmp_path)
            return out.strip(), code
        except Exception as e:
            return str(e), -1

    elif nm == "ifcfg":
        return _write_ifcfg(interface, {"dhcp": True})

    return run_cmd(f"sudo dhclient -v {safe_quote(interface)} 2>&1", timeout=30)


def _get_nm_connection(iface: str) -> str:
    """获取 NetworkManager 中指定接口的连接名称。"""
    out, _ = run_cmd(f"nmcli -t -f NAME,DEVICE con show 2>/dev/null")
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == iface:
            return parts[0]
    return iface


def get_listen_ports() -> List[Dict]:
    """Get list of listening ports."""
    ports = []
    out, _ = run_cmd("ss -tlnp 2>/dev/null")
    for line in out.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 5:
            local = parts[3] if len(parts) > 3 else ""
            process = parts[-1] if "users:" in parts[-1] else ""
            # Extract process name from users:(("name",pid=,fd=))
            m = re.search(r'\(\("([^"]+)"', process)
            proc_name = m.group(1) if m else ""
            ports.append({"protocol": "tcp", "local_address": local, "process": proc_name})
    # Also get UDP
    out, _ = run_cmd("ss -ulnp 2>/dev/null")
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 5:
            local = parts[3] if len(parts) > 3 else ""
            process = parts[-1] if "users:" in parts[-1] else ""
            m = re.search(r'\(\("([^"]+)"', process)
            proc_name = m.group(1) if m else ""
            ports.append({"protocol": "udp", "local_address": local, "process": proc_name})
    return ports


def get_network_traffic() -> Dict:
    """获取网络流量统计 (bytes/sec per interface)。"""
    result: Dict = {"interfaces": [], "total_rx": 0, "total_tx": 0}
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()[2:]  # skip headers
        for line in lines:
            parts = line.split()
            if len(parts) >= 10:
                name = parts[0].rstrip(":")
                rx = int(parts[1])
                tx = int(parts[9])
                result["total_rx"] += rx
                result["total_tx"] += tx
                result["interfaces"].append({"name": name, "rx_bytes": rx, "tx_bytes": tx})
    except Exception:
        pass
    return result
