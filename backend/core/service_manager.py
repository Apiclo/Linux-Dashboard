"""Multi-init-system service management abstraction.

Provides a unified interface for service operations across systemd, OpenRC,
and SysV init systems.  Auto-detects the active init system at import time.
"""

import os
import re
from typing import Dict, List, Tuple, Optional
from utils.helpers import run_cmd, safe_quote


class ServiceManager:
    """Abstract base for init-system service operations."""

    # Subclasses override this
    name: str = "unknown"

    def get_services(self) -> List[Dict]:
        """Return a list of service dicts with keys: name, load, active, sub, description."""
        raise NotImplementedError

    def service_action(self, name: str, action: str) -> Tuple[str, int]:
        """Perform *action* on *name*.  Returns (stdout, returncode)."""
        raise NotImplementedError

    def get_service_logs(self, name: str, lines: int = 80) -> str:
        """Return recent log lines for *name*."""
        raise NotImplementedError

    # ── Detection ──

    @staticmethod
    def detect() -> "ServiceManager":
        """Auto-detect the active init system and return the right manager."""
        if os.path.isdir("/run/systemd/system"):
            return SystemdServiceManager()
        if os.path.exists("/sbin/openrc") or os.path.exists("/usr/sbin/openrc"):
            return OpenRCServiceManager()
        if os.path.exists("/sbin/init") or os.path.exists("/usr/sbin/init"):
            # Check for SysV: /etc/init.d/ exists and no systemd/openrc
            if os.path.isdir("/etc/init.d") and not os.path.isdir("/run/systemd/system"):
                return SysVServiceManager()
        # Fallback: try to use whatever is available
        if os.path.isdir("/etc/init.d"):
            return SysVServiceManager()
        return SystemdServiceManager()  # last-resort fallback

    @staticmethod
    def has_systemd() -> bool:
        """Return True if systemd is the active init system."""
        return os.path.isdir("/run/systemd/system")

    def is_systemd(self) -> bool:
        return isinstance(self, SystemdServiceManager)


# ═══════════════════════════════════════════════════════════════
# Systemd
# ═══════════════════════════════════════════════════════════════

class SystemdServiceManager(ServiceManager):
    name = "systemd"

    def get_services(self) -> List[Dict]:
        services: List[Dict] = []
        out, _ = run_cmd(
            "systemctl list-units --type=service --all --no-pager --plain --no-legend "
            "2>/dev/null"
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                services.append({
                    "name": parts[0],
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                })
        return services

    _ALLOWED_ACTIONS = {"start", "stop", "restart", "enable", "disable", "mask", "unmask"}

    def service_action(self, name: str, action: str) -> Tuple[str, int]:
        if action not in self._ALLOWED_ACTIONS:
            return f"Invalid action: {action}", -1
        if ".." in name or "/" in name:
            return "Invalid service name", -1
        if action in ("mask", "unmask"):
            # systemd accepts mask/unmask directly
            pass
        return run_cmd(
            f"sudo systemctl {safe_quote(action)} {safe_quote(name)}",
            timeout=30
        )

    def get_service_logs(self, name: str, lines: int = 80) -> str:
        if ".." in name or "/" in name:
            return "Invalid service name"
        lines = max(10, min(lines, 500))
        out, _ = run_cmd(
            f"journalctl -u {safe_quote(name)} -n {lines} --no-pager 2>/dev/null",
            timeout=10
        )
        return out


# ═══════════════════════════════════════════════════════════════
# OpenRC  (Alpine, Gentoo, Devuan, Artix)
# ═══════════════════════════════════════════════════════════════

class OpenRCServiceManager(ServiceManager):
    name = "openrc"

    def get_services(self) -> List[Dict]:
        """Enumerate OpenRC services via rc-status."""
        services: List[Dict] = []
        # rc-status --list shows all available services
        out, _ = run_cmd("rc-status --list 2>/dev/null")
        if not out:
            # Fallback: list /etc/init.d/
            out2, _ = run_cmd("ls /etc/init.d/ 2>/dev/null")
            for name in out2.splitlines():
                name = name.strip()
                if name and not name.startswith("."):
                    status = self._svc_status(name)
                    services.append({
                        "name": name,
                        "load": "loaded",
                        "active": status,
                        "sub": "running" if status == "started" else "dead",
                        "description": "",
                    })
            return services

        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("Runlevel") or line.startswith("Dynamic"):
                continue
            # Format: "ntpd [started]" or "sshd"
            m = re.match(r'^(\S+)\s+\[(\w+)\]', line)
            if m:
                name, state = m.group(1), m.group(2)
                services.append({
                    "name": name,
                    "load": "loaded",
                    "active": "active" if state == "started" else "inactive",
                    "sub": state,
                    "description": "",
                })
        return services

    def _svc_status(self, name: str) -> str:
        out, code = run_cmd(f"rc-service {safe_quote(name)} status 2>/dev/null")
        if code == 0 and "started" in out:
            return "started"
        return "stopped"

    _ACTION_MAP = {
        "start":    "start",
        "stop":     "stop",
        "restart":  "restart",
        "enable":   "enable",   # handled specially via rc-update
        "disable":  "disable",  # handled specially via rc-update
        "mask":     "disable",  # OpenRC doesn't have mask — fallback to disable
        "unmask":   "enable",
    }

    def service_action(self, name: str, action: str) -> Tuple[str, int]:
        if action not in self._ACTION_MAP:
            return f"Invalid action: {action}", -1
        if ".." in name or "/" in name:
            return "Invalid service name", -1

        rc_action = self._ACTION_MAP[action]

        if action in ("enable", "unmask"):
            # Enable: add to default runlevel
            out, code = run_cmd(
                f"sudo rc-update add {safe_quote(name)} default 2>&1",
                timeout=15
            )
            # Also try to start it now
            if action == "enable":
                run_cmd(f"sudo rc-service {safe_quote(name)} start 2>/dev/null", timeout=15)
            return out, code
        elif action in ("disable", "mask"):
            out, code = run_cmd(
                f"sudo rc-update delete {safe_quote(name)} default 2>&1",
                timeout=15
            )
            if action == "disable":
                run_cmd(f"sudo rc-service {safe_quote(name)} stop 2>/dev/null", timeout=15)
            return out, code
        else:
            # start / stop / restart
            return run_cmd(
                f"sudo rc-service {safe_quote(name)} {rc_action} 2>&1",
                timeout=30
            )

    def get_service_logs(self, name: str, lines: int = 80) -> str:
        if ".." in name or "/" in name:
            return "Invalid service name"
        lines = max(10, min(lines, 500))
        # OpenRC services typically log to /var/log/messages or /var/log/syslog
        for logf in ["/var/log/messages", "/var/log/syslog"]:
            if os.path.exists(logf):
                out, _ = run_cmd(
                    f"sudo tail -n {lines} {safe_quote(logf)} 2>/dev/null "
                    f"| grep -i {safe_quote(name)}",
                    timeout=10
                )
                if out:
                    return out
        # Fallback: check /var/log/<service>.log
        out, _ = run_cmd(
            f"sudo tail -n {lines} /var/log/{safe_quote(name)}.log 2>/dev/null",
            timeout=10
        )
        return out or f"No logs found for {name}"


# ═══════════════════════════════════════════════════════════════
# SysV init  (legacy, containers, older Debian/Devuan)
# ═══════════════════════════════════════════════════════════════

class SysVServiceManager(ServiceManager):
    name = "sysv"

    def get_services(self) -> List[Dict]:
        services: List[Dict] = []
        out, _ = run_cmd("service --status-all 2>/dev/null")
        if not out:
            # Fallback: list init.d scripts
            out2, _ = run_cmd("ls /etc/init.d/ 2>/dev/null")
            for name in out2.splitlines():
                name = name.strip()
                if name and not name.startswith("."):
                    services.append({
                        "name": name,
                        "load": "loaded",
                        "active": "unknown",
                        "sub": "",
                        "description": "",
                    })
            return services

        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: " [ + ]  ssh" or " [ - ]  ntp"
            m = re.match(r'^\s*\[\s*([+\-?])\s*\]\s+(.+)', line)
            if m:
                state = {"+": "active", "-": "inactive", "?": "unknown"}.get(m.group(1), "unknown")
                services.append({
                    "name": m.group(2).strip(),
                    "load": "loaded",
                    "active": state,
                    "sub": m.group(1),
                    "description": "",
                })
        return services

    _ACTION_MAP = {
        "start":   "start",
        "stop":    "stop",
        "restart": "restart",
        "enable":  "enable",
        "disable": "disable",
        "mask":    "disable",   # SysV has no mask → disable
        "unmask":  "enable",
    }

    def service_action(self, name: str, action: str) -> Tuple[str, int]:
        if action not in self._ACTION_MAP:
            return f"Invalid action: {action}", -1
        if ".." in name or "/" in name:
            return "Invalid service name", -1

        if action in ("enable", "unmask"):
            # update-rc.d <name> defaults
            return run_cmd(
                f"sudo update-rc.d {safe_quote(name)} defaults 2>&1",
                timeout=15
            )
        elif action in ("disable", "mask"):
            out, code = run_cmd(
                f"sudo update-rc.d -f {safe_quote(name)} remove 2>&1",
                timeout=15
            )
            # Also stop the running service
            run_cmd(f"sudo service {safe_quote(name)} stop 2>/dev/null", timeout=15)
            return out, code
        else:
            # start / stop / restart via the service command
            return run_cmd(
                f"sudo service {safe_quote(name)} {safe_quote(action)} 2>&1",
                timeout=30
            )

    def get_service_logs(self, name: str, lines: int = 80) -> str:
        if ".." in name or "/" in name:
            return "Invalid service name"
        lines = max(10, min(lines, 500))
        for logf in ["/var/log/syslog", "/var/log/messages"]:
            if os.path.exists(logf):
                out, _ = run_cmd(
                    f"sudo tail -n {lines} {safe_quote(logf)} 2>/dev/null "
                    f"| grep -i {safe_quote(name)}",
                    timeout=10
                )
                if out:
                    return out
        out, _ = run_cmd(
            f"sudo tail -n {lines} /var/log/{safe_quote(name)}.log 2>/dev/null",
            timeout=10
        )
        return out or f"No logs found for {name}"


# ── Module-level singleton ──

_manager: Optional[ServiceManager] = None


def get_manager() -> ServiceManager:
    """Return the auto-detected ServiceManager singleton."""
    global _manager
    if _manager is None:
        _manager = ServiceManager.detect()
    return _manager


def reset_manager() -> None:
    """Reset the cached manager (useful for testing)."""
    global _manager
    _manager = None
