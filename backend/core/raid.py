"""RAID management operations."""
import re
import json
from typing import Dict, List
from utils.helpers import run_cmd, safe_quote


def get_raid_arrays() -> List[Dict]:
    """List all RAID arrays."""
    arrays = []
    out, code = run_cmd("cat /proc/mdstat")
    if code != 0:
        return arrays
    current = None
    for line in out.splitlines():
        if line.startswith("md"):
            parts = line.split()
            name = parts[0]
            level = parts[3] if len(parts) > 3 else "unknown"
            devices = [p.split("[")[0] for p in parts[4:] if "[" in p]
            current = {"name": name, "level": level, "devices": devices, "status": ""}
        elif current and "blocks" in line:
            if "_" in line or "U" in line:
                current["status"] = line.strip()
            arrays.append(current)
            current = None
    return arrays


def get_available_devices() -> List[Dict]:
    """List block devices that could be used for RAID."""
    devices = []
    out, _ = run_cmd("lsblk -Jno NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null")
    if not out:
        return devices
    try:
        data = json.loads(out)
        for dev in data.get("blockdevices", []):
            if dev.get("type") == "disk" and not dev.get("mountpoint"):
                children = dev.get("children", [])
                if not children or all(not c.get("mountpoint") for c in children):
                    devices.append({"name": dev["name"], "size": dev.get("size", ""), "path": f"/dev/{dev['name']}"})
    except (json.JSONDecodeError, KeyError):
        pass
    return devices


def create_raid(level: str, devices: List[str], name: str = "") -> Dict:
    """Create a RAID array."""
    if not devices or len(devices) < 2:
        return {"success": False, "message": "At least 2 devices required"}
    valid_levels = {"0", "1", "5", "6", "10"}
    if level not in valid_levels:
        return {"success": False, "message": f"Invalid RAID level. Supported: {', '.join(valid_levels)}"}
    for dev in devices:
        if not re.match(r'^/dev/[a-zA-Z0-9]+$', dev):
            return {"success": False, "message": f"Invalid device path: {dev}"}
    md_name = name if name else "md0"
    if not re.match(r'^md\d+$', md_name):
        md_name = f"md{md_name}" if md_name.isdigit() else "md0"
    dev_list = " ".join(safe_quote(d) for d in devices)
    out, code = run_cmd(f"sudo mdadm --create /dev/{md_name} --level={level} --raid-devices={len(devices)} {dev_list} --run", timeout=120)
    if code != 0:
        return {"success": False, "message": f"Failed to create RAID: {out}"}
    return {"success": True, "message": f"RAID array /dev/{md_name} (level {level}) created"}


def manage_raid(device: str, action: str) -> Dict:
    """Stop or remove a RAID array."""
    if not re.match(r'^/dev/md\d+$', device):
        return {"success": False, "message": "Invalid RAID device"}
    if action == "stop":
        out, code = run_cmd(f"sudo mdadm --stop {safe_quote(device)}")
    elif action == "remove":
        out, code = run_cmd(f"sudo mdadm --remove {safe_quote(device)}")
    else:
        return {"success": False, "message": f"Unknown action: {action}"}
    return {"success": code == 0, "message": out}


def get_raid_detail(device: str) -> Dict:
    """Get detailed RAID array info."""
    if not re.match(r'^/dev/md\d+$', device):
        return {"success": False, "message": "Invalid RAID device"}
    out, code = run_cmd(f"sudo mdadm --detail {safe_quote(device)}")
    return {"success": code == 0, "detail": out}
