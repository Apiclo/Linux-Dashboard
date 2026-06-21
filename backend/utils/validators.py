"""Input validation: paths, hostnames, IPs, package names, firewall commands."""
import os
import re
import shlex
from typing import Optional, Tuple, List

# ── Config paths ──

ALLOWED_CONFIG_PATHS = ["/etc/", "/usr/local/etc/", os.path.expanduser("~/")]

# Sensitive files that must not be edited through the config editor
BLOCKED_CONFIG_PATHS = [
    "/etc/shadow", "/etc/passwd", "/etc/gshadow", "/etc/group",
    "/etc/sudoers", "/etc/sudoers.d/",
    "/etc/ssh/ssh_host_",  # SSH host keys
    "/etc/ssl/private/",
]

# ── Validators ──

def validate_hostname(name: str) -> bool:
    """Validate FQDN hostname (253 char max, DNS label rules)."""
    if not name or len(name) > 253:
        return False
    return bool(re.match(
        r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
        r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$',
        name
    ))


def validate_path(path: str, allowed_prefixes: Optional[List[str]] = None) -> Tuple[bool, str]:
    """Validate a filesystem path for config file editing.

    Returns (is_valid, resolved_path_or_error_message).
    """
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


def validate_device_path(device: str) -> Tuple[bool, str]:
    """Validate a block device path.

    Accepts /dev/sdX, /dev/nvmeXnY, /dev/mapper/*, /dev/md*, /dev/vd*, etc.
    Allows dots and hyphens for LVM logical volumes and by-id/by-uuid paths.
    """
    if not device or len(device) > 512:
        return False, "Invalid device path"
    if not re.match(r'^(/dev/)?[a-zA-Z0-9][a-zA-Z0-9._\-/]*$', device):
        return False, f"Invalid device path: {device}"
    return True, ""


# ── Firewall command whitelist ──

ALLOWED_FW_COMMANDS = {
    "ufw": ["status", "enable", "disable", "allow", "deny", "reload", "reset"],
    "iptables": ["-L", "-S", "-F"],
    "nft": ["list", "flush"],
    "firewall-cmd": ["--state", "--list-all", "--reload"],
    "ip": ["addr", "link", "route", "neigh"],
}


def validate_fw_command(cmd_str: str) -> Tuple[bool, str]:
    """Validate a firewall/network command against the whitelist.

    Returns (is_valid, safe_quoted_command_or_error_message).
    """
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        return False, "Invalid command syntax"
    if not parts:
        return False, "Empty command"
    cmd = parts[0]
    if cmd not in ALLOWED_FW_COMMANDS:
        return False, f"Command not allowed: {cmd}"
    subcommands = ALLOWED_FW_COMMANDS[cmd]
    if len(parts) < 2 or parts[1] not in subcommands:
        subcmd = parts[1] if len(parts) > 1 else "none"
        return False, f"Subcommand not allowed for {cmd}: {subcmd}"
    for ch in [';', '|', '&', '$', '`', '(', ')', '{', '}', '\n', '\r', '>', '<', '#']:
        if ch in cmd_str:
            return False, f"Dangerous character: {repr(ch)}"
    return True, " ".join(shlex.quote(p) for p in parts)
