"""Service operations."""
import os
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def _has_systemd() -> bool:
    """Check if the system uses systemd."""
    return os.path.isdir("/run/systemd/system") or os.path.exists("/proc/1/comm")


def _require_systemd() -> tuple:
    """Return (ok, error_msg) if systemd is not available."""
    if not _has_systemd():
        return False, "This system does not use systemd. Service management is not available."
    return True, ""


def get_services() -> List[Dict]:
    ok, msg = _require_systemd()
    if not ok:
        return [{"error": msg}]
    services: List[Dict] = []
    out, _ = run_cmd("systemctl list-units --type=service --all --no-pager --plain --no-legend 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            services.append({"name": parts[0], "load": parts[1], "active": parts[2], "sub": parts[3], "description": " ".join(parts[4:]) if len(parts) > 4 else ""})
    return services


def service_action(name: str, action: str) -> Tuple[str, int]:
    ok, msg = _require_systemd()
    if not ok:
        return msg, -1
    allowed = ("start", "stop", "restart", "enable", "disable", "mask", "unmask")
    if action not in allowed: return f"Invalid action", -1
    if ".." in name or "/" in name: return "Invalid service name", -1
    return run_cmd(f"sudo systemctl {safe_quote(action)} {safe_quote(name)}")


def get_service_logs(name: str, lines: int = 80) -> str:
    ok, msg = _require_systemd()
    if not ok:
        return msg
    if ".." in name or "/" in name: return "Invalid service name"
    lines = max(10, min(lines, 500))
    out, _ = run_cmd(f"journalctl -u {safe_quote(name)} -n {lines} --no-pager 2>/dev/null", timeout=10)
    return out
