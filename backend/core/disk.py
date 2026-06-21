"""Disk management."""
import os
import json
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote, validate_device_path, atomic_sudo_write


def get_block_devices() -> List[Dict]:
    out, _ = run_cmd("lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL,UUID 2>/dev/null")
    if out:
        try:
            data = json.loads(out)
            return [_parse(d) for d in data.get("blockdevices", [])]
        except Exception: pass
    return []


def _parse(dev: Dict) -> Dict:
    r = {"name": dev.get("name", ""), "size": dev.get("size", ""), "type": dev.get("type", ""), "mountpoint": dev.get("mountpoint", ""), "fstype": dev.get("fstype", ""), "model": dev.get("model", ""), "uuid": dev.get("uuid", ""), "children": []}
    r["children"] = [_parse(c) for c in dev.get("children", [])]
    return r


def get_fstab() -> str:
    try:
        with open("/etc/fstab") as f: return f.read()
    except Exception: return ""


def save_fstab(content: str) -> bool:
    ok, _ = atomic_sudo_write('/etc/fstab', content)
    return ok


def mount_device(device: str, mountpoint: str, fstype: str = "auto") -> Tuple[str, int]:
    if not device or not mountpoint:
        return "设备和挂载点不能为空", -1
    # Validate device path
    valid, msg = validate_device_path(device)
    if not valid:
        return msg, -1
    # Validate mountpoint (no traversal)
    real_mp = os.path.realpath(os.path.expanduser(mountpoint))
    if ".." in mountpoint or not real_mp.startswith("/"):
        return f"Invalid mountpoint: {mountpoint}", -1
    run_cmd(f"sudo mkdir -p {safe_quote(real_mp)}")
    return run_cmd(f"sudo mount {safe_quote(device)} {safe_quote(real_mp)} -t {safe_quote(fstype)}")


def umount_device(target: str) -> Tuple[bool, str]:
    if not target: return False, "参数不能为空"
    out, code = run_cmd(f"sudo umount {safe_quote(target)}")
    return (True, f"已卸载 {target}") if code == 0 else (False, f"卸载失败: {out}")


def get_disk_usage() -> str:
    # Try GNU df first, fallback to basic df
    out, code = run_cmd("df -h --output=source,size,used,avail,pcent,target -x tmpfs -x devtmpfs -x efivarfs 2>/dev/null")
    if code != 0 or not out:
        # Fallback for BusyBox/Alpine
        out, _ = run_cmd("df -h 2>/dev/null")
    return out


def get_disk_usage_structured() -> List[Dict]:
    """Return structured disk usage data as a list of dicts."""
    out, code = run_cmd("df -B1 --output=source,size,used,avail,pcent,target -x tmpfs -x devtmpfs -x efivarfs 2>/dev/null")
    if code != 0:
        out, _ = run_cmd("df -B1 2>/dev/null")
    devices: List[Dict] = []
    for line in out.splitlines():
        if line.startswith("Filesystem") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 5:
            devices.append({
                "source": parts[0],
                "size_bytes": int(parts[1]) if len(parts) > 1 and (parts[1].isdigit() or (parts[1].startswith("-") and parts[1][1:].isdigit())) else 0,
                "used_bytes": int(parts[2]) if len(parts) > 2 and (parts[2].isdigit() or (parts[2].startswith("-") and parts[2][1:].isdigit())) else 0,
                "avail_bytes": int(parts[3]) if len(parts) > 3 and (parts[3].isdigit() or (parts[3].startswith("-") and parts[3][1:].isdigit())) else 0,
                "use_pct": parts[4] if len(parts) > 4 else "",
                "target": parts[5] if len(parts) > 5 else "",
            })
    return devices
