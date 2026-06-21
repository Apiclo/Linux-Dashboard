"""Common helper functions."""
import os
import re
import shlex
import subprocess
import logging
import tempfile
from typing import Optional, Tuple, List
from functools import wraps
from flask import request, jsonify, session

log = logging.getLogger("helpers")

ALLOWED_CONFIG_PATHS = ["/etc/", "/usr/local/etc/", os.path.expanduser("~/")]

# Sensitive files that must not be edited through the config editor
BLOCKED_CONFIG_PATHS = [
    "/etc/shadow", "/etc/passwd", "/etc/gshadow", "/etc/group",
    "/etc/sudoers", "/etc/sudoers.d/",
    "/etc/ssh/ssh_host_",  # SSH host keys
    "/etc/ssl/private/",
]


def run_cmd(cmd: str, timeout: int = 30) -> Tuple[str, int]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", -1
    except Exception as e:
        return str(e), -1


def safe_quote(value: str) -> str:
    return shlex.quote(value.strip())


def validate_hostname(name: str) -> bool:
    if not name or len(name) > 253:
        return False
    return bool(re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', name))


def validate_path(path: str, allowed_prefixes: Optional[List[str]] = None) -> Tuple[bool, str]:
    if allowed_prefixes is None:
        allowed_prefixes = ALLOWED_CONFIG_PATHS
    real = os.path.realpath(os.path.expanduser(path))
    # Check blocked paths first
    for blocked in BLOCKED_CONFIG_PATHS:
        if real.startswith(os.path.realpath(blocked)):
            return False, "Access denied: sensitive file"
    for prefix in allowed_prefixes:
        if real.startswith(os.path.realpath(prefix)):
            return True, real
    return False, f"Path not allowed: {real}"


def safe_temp_file(suffix: str = "", prefix: str = "lt_", content: str = "") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    try:
        if content:
            os.write(fd, content.encode())
    finally:
        os.close(fd)
    return path


def safe_api(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            log.error(f"API error in {f.__name__}: {e}", exc_info=True)
            return jsonify({"success": False, "message": "Internal server error"}), 500
    return wrapper


def validate_json(required_fields: Optional[List[str]] = None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({"success": False, "message": "Request body must be JSON"}), 400
            if required_fields:
                missing = [k for k in required_fields if k not in data]
                if missing:
                    return jsonify({"success": False, "message": f"Missing: {', '.join(missing)}"}), 400
            return f(data, *args, **kwargs)
        return wrapper
    return decorator


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("authenticated"):
            return f(*args, **kwargs)
        return jsonify({"success": False, "message": "未登录", "code": 401}), 401
    return wrapper


def validate_package_name(pkg: str) -> Tuple[bool, str]:
    """Validate package name to prevent command injection."""
    if not pkg or len(pkg) > 256:
        return False, "Invalid package name"
    if not re.match(r'^[a-zA-Z0-9._+\-:~^]+$', pkg):
        return False, f"Invalid characters in package name: {pkg}"
    return True, ""


def validate_ip(ip: str) -> bool:
    """Validate IPv4 address."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


ALLOWED_FW_COMMANDS = {
    "ufw": ["status", "enable", "disable", "allow", "deny", "reload", "reset"],
    "iptables": ["-L", "-S", "-F"],
    "nft": ["list", "flush"],
    "firewall-cmd": ["--state", "--list-all", "--reload"],
    "ip": ["addr", "link", "route", "neigh"],
}


def validate_fw_command(cmd_str: str) -> Tuple[bool, str]:
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        return False, "Invalid command syntax"
    if not parts:
        return False, "Empty command"
    cmd = parts[0]
    if cmd not in ALLOWED_FW_COMMANDS:
        return False, f"Command not allowed: {cmd}"
    # 验证子命令在白名单中
    subcommands = ALLOWED_FW_COMMANDS[cmd]
    if len(parts) < 2 or parts[1] not in subcommands:
        subcmd = parts[1] if len(parts) > 1 else "none"
        return False, f"Subcommand not allowed for {cmd}: {subcmd}"
    for ch in [';', '|', '&', '$', '`', '(', ')', '{', '}', '\n', '\r', '>', '<', '#']:
        if ch in cmd_str:
            return False, f"Dangerous character: {repr(ch)}"
    return True, " ".join(shlex.quote(p) for p in parts)
