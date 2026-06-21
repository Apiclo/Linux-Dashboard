"""VLAN and bridge management."""
import re
import json
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def get_vlans() -> List[Dict]:
    """获取所有 VLAN 子接口。"""
    vlans = []
    out, _ = run_cmd("ip -d link show type vlan 2>/dev/null")
    current = {}
    for line in out.splitlines():
        line = line.strip()
        if re.match(r'^\d+:', line):
            if current:
                vlans.append(current)
            parts = line.split(": ")
            name = parts[1].split("@")[0] if len(parts) > 1 else ""
            current = {"name": name, "id": "", "parent": "", "protocol": "802.1Q"}
        elif "vlan protocol" in line:
            m = re.search(r'vlan protocol (\S+)', line)
            if m: current["protocol"] = m.group(1)
        elif "id" in line and "vlan" in line:
            m = re.search(r'id (\d+)', line)
            if m: current["id"] = m.group(1)
    if current:
        vlans.append(current)

    # Also check /proc/net/vlan
    if not vlans:
        out2, _ = run_cmd("cat /proc/net/vlan/config 2>/dev/null")
        for line in out2.splitlines():
            parts = line.split("|")
            if len(parts) >= 3 and "VLAN" not in line:
                vlan = {"name": parts[0].strip(), "id": parts[1].strip(), "parent": parts[2].strip()}
                vlans.append(vlan)

    return vlans


def create_vlan(parent: str, vlan_id: int, name: str = "") -> Tuple[str, int]:
    if not re.match(r'^[a-zA-Z0-9._-]+$', parent):
        return "Invalid parent interface", -1
    if not (1 <= vlan_id <= 4094):
        return "VLAN ID must be 1-4094", -1
    vname = name or f"{parent}.{vlan_id}"
    return run_cmd(
        f"sudo ip link add link {safe_quote(parent)} name {safe_quote(vname)} type vlan id {vlan_id} && "
        f"sudo ip link set {safe_quote(vname)} up",
        timeout=10
    )


def delete_vlan(name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo ip link delete {safe_quote(name)} 2>&1", timeout=10)


def get_bridges() -> List[Dict]:
    bridges = []
    out, _ = run_cmd("ip -j link show type bridge 2>/dev/null")
    if out.strip():
        try:
            data = json.loads(out)
            for br in data:
                br_info = {"name": br.get("ifname", ""), "members": [], "up": "UP" in br.get("flags", [])}
                # Get bridge members
                mem_out, _ = run_cmd(f"ip -j link show master {safe_quote(br_info['name'])} 2>/dev/null")
                if mem_out.strip():
                    try:
                        members = json.loads(mem_out)
                        br_info["members"] = [m.get("ifname", "") for m in members]
                    except json.JSONDecodeError:
                        pass
                bridges.append(br_info)
        except json.JSONDecodeError:
            pass

    # Fallback: brctl
    if not bridges:
        out2, _ = run_cmd("brctl show 2>/dev/null")
        for line in out2.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 1:
                bridges.append({"name": parts[0], "members": parts[3:] if len(parts) > 3 else [], "up": False})
    return bridges


def create_bridge(name: str) -> Tuple[str, int]:
    if not re.match(r'^br[a-zA-Z0-9]*$', name):
        return "Bridge name must start with 'br' followed by alphanumeric chars", -1
    return run_cmd(
        f"sudo ip link add {safe_quote(name)} type bridge && sudo ip link set {safe_quote(name)} up",
        timeout=10
    )


def bridge_add_member(bridge: str, iface: str) -> Tuple[str, int]:
    return run_cmd(
        f"sudo ip link set {safe_quote(iface)} master {safe_quote(bridge)} && sudo ip link set {safe_quote(iface)} up",
        timeout=10
    )


def bridge_remove_member(iface: str) -> Tuple[str, int]:
    return run_cmd(f"sudo ip link set {safe_quote(iface)} nomaster 2>&1", timeout=10)


def delete_bridge(name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo ip link delete {safe_quote(name)} 2>&1", timeout=10)
