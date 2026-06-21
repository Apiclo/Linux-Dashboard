"""Disk management."""
import os
import re
import json
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


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
    from utils.helpers import safe_temp_file
    tmp = safe_temp_file(suffix=".fstab", content=content)
    try:
        _, code = run_cmd(f"sudo cp {safe_quote(tmp)} /etc/fstab")
        return code == 0
    finally:
        try: os.remove(tmp)
        except OSError: pass


def mount_device(device: str, mountpoint: str, fstype: str = "auto") -> Tuple[str, int]:
    if not device or not mountpoint:
        return "设备和挂载点不能为空", -1
    # Validate device path
    if not re.match(r'^/dev/[a-zA-Z0-9_/]+$', device):
        return f"Invalid device path: {device}", -1
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
