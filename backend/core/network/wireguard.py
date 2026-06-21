"""WireGuard management."""
import re
import json
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def get_wireguard_interfaces() -> List[Dict]:
    wgs = []
    out, _ = run_cmd("ip -j link show type wireguard 2>/dev/null")
    if out.strip():
        try:
            data = json.loads(out)
            for wg in data:
                info = {"name": wg.get("ifname", ""), "up": "UP" in wg.get("flags", [])}
                # get wg show info
                wg_out, _ = run_cmd(f"sudo wg show {safe_quote(info['name'])} 2>/dev/null")
                for line in wg_out.splitlines():
                    if "listening port" in line:
                        info["port"] = line.split(":")[-1].strip()
                    elif "peer:" in line:
                        if "peers" not in info:
                            info["peers"] = []
                        info["peers"].append(line.split(":")[-1].strip())
                wgs.append(info)
        except json.JSONDecodeError:
            pass
    return wgs


def wireguard_check() -> Tuple[bool, str]:
    _, code = run_cmd("which wg 2>/dev/null")
    if code != 0:
        return False, "wireguard-tools 未安装"
    mod_loaded, _ = run_cmd("lsmod | grep wireguard 2>/dev/null")
    if not mod_loaded.strip():
        return False, "wireguard 内核模块未加载 (modprobe wireguard)"
    return True, "WireGuard 可用"


def create_wireguard(name: str) -> Tuple[str, int]:
    if not re.match(r'^wg\d+$', name):
        return "WireGuard interface must be named wg0, wg1, ...", -1
    return run_cmd(f"sudo ip link add {safe_quote(name)} type wireguard 2>&1", timeout=10)


def delete_wireguard(name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo ip link delete {safe_quote(name)} 2>&1", timeout=10)
