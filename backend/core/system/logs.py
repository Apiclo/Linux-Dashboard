"""Logs, NTP, ulimits, kernel modules, cron, dmesg, audit."""
import os
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote, atomic_sudo_write


def get_journal_logs(lines: int = 100, unit: str = "", priority: str = "") -> str:
    """Read system journal logs."""
    lines = max(10, min(lines, 500))
    cmd = f"journalctl --no-pager -n {lines}"
    if unit:
        cmd += f" -u {safe_quote(unit)}"
    if priority:
        cmd += f" -p {safe_quote(priority)}"
    cmd += " 2>/dev/null"
    out, _ = run_cmd(cmd, timeout=15)
    return out


def get_ntp_status() -> Dict:
    """Get NTP/chrony time sync status."""
    out, _ = run_cmd("timedatectl show --property=NTP --property=NTPSynchronized")
    result = {"ntp_enabled": False, "synced": False}
    for line in out.splitlines():
        if "NTP=yes" in line: result["ntp_enabled"] = True
        if "NTPSynchronized=yes" in line: result["synced"] = True
    # Get active time service
    for svc in ["chronyd", "systemd-timesyncd", "ntpd"]:
        _, code = run_cmd(f"systemctl is-active {svc}")
        if code == 0:
            result["service"] = svc
            break
    return result


def toggle_ntp(enable: bool) -> Dict:
    """Enable or disable NTP."""
    action = "true" if enable else "false"
    out, code = run_cmd(f"sudo timedatectl set-ntp {action}")
    return {"success": code == 0, "message": out or ("NTP enabled" if enable else "NTP disabled")}


def get_ulimits() -> Dict:
    """Read current ulimits from /etc/security/limits.conf and running limits."""
    limits = {"file": "", "running": ""}
    try:
        with open("/etc/security/limits.conf") as f:
            limits["file"] = f.read()
    except Exception:
        limits["file"] = "# Could not read /etc/security/limits.conf"
    # Read running limits for current process
    out, _ = run_cmd("ulimit -a 2>/dev/null")
    limits["running"] = out
    return limits


def save_ulimits(content: str) -> Dict:
    """Save /etc/security/limits.conf."""
    ok, msg = atomic_sudo_write('/etc/security/limits.conf', content)
    return {"success": ok, "message": "Limits updated" if ok else f"Failed to update limits: {msg}"}


def get_kernel_modules() -> List[Dict]:
    """List loaded kernel modules."""
    modules = []
    out, _ = run_cmd("lsmod")
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            modules.append({
                "name": parts[0],
                "size": parts[1],
                "used_by": int(parts[2]) if parts[2].isdigit() else 0,
                "used_by_list": " ".join(parts[3:]) if len(parts) > 3 else "",
            })
    return modules


def manage_kernel_module(name: str, action: str) -> Dict:
    """Load or unload a kernel module."""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', name):
        return {"success": False, "message": "Invalid module name"}
    if action == "load":
        out, code = run_cmd(f"sudo modprobe {safe_quote(name)}")
    elif action == "unload":
        out, code = run_cmd(f"sudo modprobe -r {safe_quote(name)}")
    else:
        return {"success": False, "message": f"Unknown action: {action}"}
    return {"success": code == 0, "message": out or f"Module {name} {action}ed"}


def get_crontab(user: str = "") -> Tuple[str, str]:
    """获取 crontab 内容。user 为空则获取当前用户。"""
    if user:
        out, code = run_cmd(f"sudo crontab -u {safe_quote(user)} -l 2>/dev/null", timeout=10)
    else:
        out, code = run_cmd("crontab -l 2>/dev/null", timeout=10)
    return out.strip(), user or os.environ.get("USER", "root")


def set_crontab(content: str, user: str = "") -> Tuple[str, int]:
    """设置 crontab 内容。"""
    tmp = safe_temp_file(suffix=".cron", content=content)
    if user:
        out, code = run_cmd(f"sudo crontab -u {safe_quote(user)} {safe_quote(tmp)} 2>&1", timeout=10)
    else:
        out, code = run_cmd(f"crontab {safe_quote(tmp)} 2>&1", timeout=10)
    os.remove(tmp)
    return out.strip(), code


def get_dmesg(lines: int = 100, level: str = "") -> str:
    cmd = "sudo dmesg"
    if level:
        cmd += f" -l {safe_quote(level)}"
    out, _ = run_cmd(f"{cmd} 2>/dev/null | tail -{lines}", timeout=10)
    return out


def get_audit_logs(lines: int = 100) -> str:
    out, _ = run_cmd(f"sudo ausearch -m all --start recent 2>/dev/null | tail -{lines} || sudo cat /var/log/audit/audit.log 2>/dev/null | tail -{lines}", timeout=15)
    return out
