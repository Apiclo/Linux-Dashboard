"""Systemd timer management and cron visualization."""
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def list_systemd_timers() -> Dict:
    """列出所有 systemd timer 及其状态。"""
    out, _ = run_cmd("systemctl list-timers --all --no-pager --no-legend 2>/dev/null")
    timers = []
    for line in out.splitlines():
        parts = line.split(None, 8)
        if len(parts) >= 8:
            timers.append({
                "next": parts[0],
                "left": parts[1],
                "last": parts[2],
                "passed": parts[3],
                "unit": parts[4],
                "activates": parts[5],
            })
    return {"timers": timers, "count": len(timers)}


def get_timer_detail(name: str) -> Dict:
    """获取 timer 详细信息。"""
    if ".." in name or "/" in name:
        return {"error": "Invalid timer name"}

    result: Dict = {"timer": name}

    # systemctl show
    out, _ = run_cmd(f"systemctl show {safe_quote(name)} --no-pager 2>/dev/null")
    props = {
        "ActiveState": "active",
        "UnitFileState": "enabled",
        "OnUnitActiveSec": "on_active_sec",
        "OnBootSec": "on_boot_sec",
        "OnCalendar": "on_calendar",
        "RandomizedDelayUSec": "randomized_delay",
        "Persistent": "persistent",
        "NextElapseUSecRealtime": "next_elapse",
        "LastTriggerUSec": "last_trigger",
    }
    for line in out.splitlines():
        for prop, key in props.items():
            if line.startswith(f"{prop}="):
                val = line.split("=", 1)[1].strip()
                if val:
                    result[key] = val
                break

    # Get the associated service unit
    svc_out, _ = run_cmd(f"systemctl show {safe_quote(name)} -p Unit --no-pager 2>/dev/null")
    if svc_out.startswith("Unit="):
        result["activates"] = svc_out.split("=", 1)[1].strip()

    return result


def timer_action(name: str, action: str) -> Tuple[bool, str]:
    """管理 systemd timer (start/stop/enable/disable)。"""
    if ".." in name or "/" in name:
        return False, "Invalid timer name"
    allowed = {"start", "stop", "enable", "disable", "restart"}
    if action not in allowed:
        return False, f"Invalid action: {action}"
    out, code = run_cmd(f"sudo systemctl {safe_quote(action)} {safe_quote(name)} 2>&1", timeout=30)
    return code == 0, out.strip()


def parse_crontab() -> Dict:
    """解析 crontab 并返回结构化数据。"""
    out, _ = run_cmd("crontab -l 2>/dev/null")
    entries = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Handle env vars
        if "=" in line and not any(line.startswith(c) for c in "0123456789*@"):
            continue
        parts = line.split(None, 5)
        if len(parts) >= 6:
            entries.append({
                "minute": parts[0],
                "hour": parts[1],
                "day": parts[2],
                "month": parts[3],
                "weekday": parts[4],
                "command": parts[5][:200],
                "raw": line,
            })
    return {"entries": entries, "count": len(entries)}


def get_system_crontabs() -> Dict:
    """列出系统级 crontab 文件。"""
    result: Dict = {"files": []}
    paths = [
        "/etc/crontab",
        "/etc/cron.d",
        "/etc/cron.hourly",
        "/etc/cron.daily",
        "/etc/cron.weekly",
        "/etc/cron.monthly",
    ]
    for p in paths:
        import os
        if os.path.isfile(p):
            try:
                with open(p) as f:
                    result["files"].append({
                        "path": p,
                        "content": f.read()[:2000],
                        "type": "file",
                    })
            except Exception:
                pass
        elif os.path.isdir(p):
            try:
                scripts = sorted(os.listdir(p))[:20]
                result["files"].append({
                    "path": p,
                    "scripts": scripts,
                    "type": "dir",
                })
            except Exception:
                pass
    return result
