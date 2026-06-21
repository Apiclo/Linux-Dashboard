"""Network bonding (modes 0-6)."""
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


BOND_MODES = {
    "0": "balance-rr (轮询)",
    "1": "active-backup (主备)",
    "2": "balance-xor (异或)",
    "3": "broadcast (广播)",
    "4": "802.3ad (LACP)",
    "5": "balance-tlb (自适应发送)",
    "6": "balance-alb (自适应负载)",
}


BOND_OPTIONS = {
    "miimon": {"desc": "链路监测间隔 (ms)", "default": "100", "values": ["50", "100", "200", "500"]},
    "xmit_hash_policy": {"desc": "传输哈希策略", "default": "layer2", "values": ["layer2", "layer2+3", "layer3+4", "encap2+3", "encap3+4"]},
    "lacp_rate": {"desc": "LACP 速率 (仅 802.3ad)", "default": "slow", "values": ["slow", "fast"]},
    "arp_interval": {"desc": "ARP 监测间隔 (ms, 仅 mode 0/1)", "default": "0", "values": ["0", "100", "500", "1000"]},
    "arp_ip_target": {"desc": "ARP 目标 IP (仅 mode 0/1)", "default": "", "values": []},
    "downdelay": {"desc": "故障检测延迟 (ms)", "default": "0", "values": ["0", "200", "500", "1000"]},
    "updelay": {"desc": "恢复检测延迟 (ms)", "default": "0", "values": ["0", "200", "500", "1000"]},
    "fail_over_mac": {"desc": "MAC 故障转移策略", "default": "none", "values": ["none", "active", "follow"]},
}


def get_bonds() -> List[Dict]:
    """获取现有 bond 接口。"""
    bonds = []
    out, _ = run_cmd("ls /sys/class/net/ 2>/dev/null")
    for iface in out.splitlines():
        iface = iface.strip()
        if iface.startswith("bond"):
            bond_info = {"name": iface, "slaves": [], "mode": "", "status": ""}
            # 读 slaves
            slave_out, _ = run_cmd(f"cat /sys/class/net/{iface}/bonding/slaves 2>/dev/null")
            if slave_out:
                bond_info["slaves"] = [s.strip() for s in slave_out.split()]
            # 读 mode
            mode_out, _ = run_cmd(f"cat /sys/class/net/{iface}/bonding/mode 2>/dev/null")
            if mode_out:
                mode_str = mode_out.strip().split()[-1] if mode_out.strip() else ""
                bond_info["mode"] = mode_str
            # 检查状态
            stat_out, _ = run_cmd(f"ip link show {iface} 2>/dev/null | grep -o 'state [A-Z]*'")
            bond_info["status"] = stat_out.replace("state ", "") if stat_out else "unknown"
            bonds.append(bond_info)
    return bonds


def create_bond(name: str, slaves: List[str], mode: str = "1",
                ip_addr: str = "", gateway: str = "") -> Tuple[str, int]:
    """创建网络绑定接口。"""
    if not re.match(r'^bond\d+$', name):
        return f"Invalid bond name: {name}", -1
    if len(slaves) < 2:
        return "At least 2 slaves required", -1
    if mode not in BOND_MODES:
        return f"Invalid mode: {mode}", -1

    cmds = []
    # 卸载已有 bond（如存在）
    cmds.append(f"sudo ip link set {safe_quote(name)} down 2>/dev/null || true")
    # 释放从接口
    for s in slaves:
        cmds.append(f"sudo ip link set {safe_quote(s)} nomaster 2>/dev/null || true")
    # 加载 bonding 模块
    cmds.append("sudo modprobe bonding 2>/dev/null || true")
    # 创建 bond
    cmds.append(
        f"sudo ip link add {safe_quote(name)} type bond mode {mode} miimon 100 2>&1 || "
        f"echo 'bond may already exist, configuring...' 2>&1"
    )
    # 添加从接口
    for s in slaves:
        cmds.append(f"sudo ip link set {safe_quote(s)} down && "
                    f"sudo ip link set {safe_quote(s)} master {safe_quote(name)} && "
                    f"sudo ip link set {safe_quote(s)} up")
    # 启动 bond
    cmds.append(f"sudo ip link set {safe_quote(name)} up")
    if ip_addr:
        cmds.append(f"sudo ip addr add {safe_quote(ip_addr)} dev {safe_quote(name)} 2>/dev/null || true")
    if gateway:
        cmds.append(f"sudo ip route add default via {safe_quote(gateway)} dev {safe_quote(name)} 2>/dev/null || true")

    return run_cmd(" && ".join(cmds), timeout=30)


def delete_bond(name: str) -> Tuple[str, int]:
    """删除 bond 接口。"""
    if not re.match(r'^bond\d+$', name):
        return f"Invalid bond name: {name}", -1
    return run_cmd(
        f"sudo ip link set {safe_quote(name)} down 2>/dev/null && "
        f"sudo ip link delete {safe_quote(name)} 2>&1",
        timeout=10
    )


def get_available_slaves() -> List[str]:
    """获取可用作 bond slave 的物理接口（排除 bond、lo、veth、docker 等）。"""
    slaves = []
    out, _ = run_cmd("ls /sys/class/net/ 2>/dev/null")
    for iface in out.splitlines():
        iface = iface.strip()
        if iface in ("lo",) or iface.startswith(("bond", "veth", "docker", "br-", "virbr", "vnet", "wg", "tun", "tap", "flannel", "cali")):
            continue
        slaves.append(iface)
    return slaves


def get_bond_options() -> Dict:
    return BOND_OPTIONS


def create_bond_advanced(name: str, slaves: List[str], mode: str = "1",
                         options: Dict[str, str] = None) -> Tuple[str, int]:
    if not re.match(r'^bond\d+$', name):
        return "Invalid bond name", -1
    if len(slaves) < 2:
        return "At least 2 slaves required", -1

    cmd_parts = [f"sudo ip link add {safe_quote(name)} type bond mode {mode}"]
    if options:
        for k, v in options.items():
            if v and k in BOND_OPTIONS:
                cmd_parts.append(f"{k} {safe_quote(v)}")
    cmd_parts.append("2>&1")

    out, code = run_cmd(" ".join(cmd_parts), timeout=15)
    if code != 0:
        return out.strip(), code

    # Add slaves
    for s in slaves:
        run_cmd(f"sudo ip link set {safe_quote(s)} down 2>/dev/null", timeout=5)
        run_cmd(f"sudo ip link set {safe_quote(s)} master {safe_quote(name)} 2>/dev/null", timeout=5)
        run_cmd(f"sudo ip link set {safe_quote(s)} up 2>/dev/null", timeout=5)

    run_cmd(f"sudo ip link set {safe_quote(name)} up 2>/dev/null", timeout=5)
    return f"Bond {name} created with mode {mode}", 0
