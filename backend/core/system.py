"""System operations."""
import os
import re
import shlex
import psutil
import platform
import socket
from typing import Dict, List, Tuple, Optional
from utils.helpers import run_cmd, safe_quote, validate_hostname, safe_temp_file


def _get_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            s = float(f.read().split()[0])
        d, h, m = int(s // 86400), int((s % 86400) // 3600), int((s % 3600) // 60)
        return f"{d}天 {h}小时 {m}分钟" if d else f"{h}小时 {m}分钟"
    except Exception:
        return "Unknown"


def get_system_info() -> Dict:
    info: Dict = {}
    info["hostname"] = socket.gethostname()
    info["os_name"] = "Unknown"
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="): info["os_name"] = line.split("=", 1)[1].strip().strip('"'); break
    except Exception: pass
    info["kernel"] = platform.release()
    info["arch"] = platform.machine()
    info["cpu"] = "Unknown"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line: info["cpu"] = line.split(":", 1)[1].strip(); break
    except Exception: pass
    info["cpu_cores"] = psutil.cpu_count(logical=False) or 0
    info["cpu_threads"] = psutil.cpu_count(logical=True) or 0
    mem = psutil.virtual_memory()
    info["ram_total_gb"] = round(mem.total / (1024**3), 1)
    info["ram_used_gb"] = round(mem.used / (1024**3), 1)
    info["ram_percent"] = mem.percent
    disk = psutil.disk_usage("/")
    info["disk_total_gb"] = round(disk.total / (1024**3), 1)
    info["disk_used_gb"] = round(disk.used / (1024**3), 1)
    info["disk_percent"] = disk.percent
    info["uptime"] = _get_uptime()
    info["desktop"] = os.environ.get("XDG_CURRENT_DESKTOP", "Unknown")
    info["shell"] = os.environ.get("SHELL", "Unknown")
    tz, _ = run_cmd("timedatectl show --property=Timezone --value")
    info["timezone"] = tz or "Unknown"
    loc, _ = run_cmd("locale | grep LANG=")
    info["locale"] = loc.split("=")[-1].strip('"') if loc else "Unknown"
    return info


def get_timezone_list():
    out, _ = run_cmd("timedatectl list-timezones")
    return out.splitlines() if out else ["UTC"]


def get_locale_list():
    out, _ = run_cmd("locale -a")
    return sorted(out.splitlines()) if out else ["en_US.UTF-8"]


def set_hostname(name: str) -> Tuple[str, int]:
    if not validate_hostname(name): return "Invalid hostname", -1
    return run_cmd(f"sudo hostnamectl set-hostname {safe_quote(name)}")


def set_timezone(tz: str) -> Tuple[str, int]:
    return run_cmd(f"sudo timedatectl set-timezone {safe_quote(tz)}")


def set_locale(loc: str) -> Tuple[str, int]:
    return run_cmd(f"sudo localectl set-locale LANG={safe_quote(loc)}")


def get_sysctl_params(q: str = "") -> Dict[str, str]:
    params: Dict[str, str] = {}
    cmd = "sysctl -a 2>/dev/null"
    if q:
        cmd = f"sysctl -a 2>/dev/null | grep -i {safe_quote(q)}"
    out, _ = run_cmd(cmd, timeout=10)
    for line in out.splitlines():
        if " = " in line:
            k, v = line.split(" = ", 1)
            params[k.strip()] = v.strip()
    return params


def set_sysctl_param(key: str, value: str) -> Tuple[str, int]:
    import re
    if not re.match(r'^[a-zA-Z0-9._]+$', key): return "Invalid parameter name", -1
    return run_cmd(f"sudo sysctl {safe_quote(key)}={safe_quote(value)}")


def get_hosts() -> str:
    try:
        with open("/etc/hosts") as f: return f.read()
    except Exception: return ""


def save_hosts(content: str) -> bool:
    tmp = safe_temp_file(suffix=".hosts", content=content)
    try:
        _, code = run_cmd(f"sudo cp {safe_quote(tmp)} /etc/hosts")
        return code == 0
    finally:
        try: os.remove(tmp)
        except OSError: pass


def get_ssh_config() -> Dict:
    """Read key SSH daemon configuration."""
    config = {"port": "22", "permit_root_login": "yes", "password_auth": "yes", "pubkey_auth": "yes"}
    try:
        with open("/etc/ssh/sshd_config") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                key, val = parts[0].lower(), parts[1].lower()
                if key == "port": config["port"] = val
                elif key == "permitrootlogin": config["permit_root_login"] = val
                elif key == "passwordauthentication": config["password_auth"] = val
                elif key == "pubkeyauthentication": config["pubkey_auth"] = val
    except Exception:
        pass
    return config


def save_ssh_config(cfg: Dict) -> Dict:
    """Update SSH daemon configuration."""
    mapping = {"port": "Port", "permit_root_login": "PermitRootLogin", "password_auth": "PasswordAuthentication", "pubkey_auth": "PubkeyAuthentication"}
    lines = []
    try:
        with open("/etc/ssh/sshd_config") as f:
            lines = f.readlines()
    except Exception:
        return {"success": False, "message": "Cannot read sshd_config"}

    updated_keys: set = set()
    new_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        replaced = False
        for cfg_key, ssh_key in mapping.items():
            if cfg_key in cfg and not stripped.startswith("#") and (stripped.lower().startswith(ssh_key.lower() + " ") or stripped.lower().startswith(ssh_key.lower() + "\t")):
                new_lines.append(f"{ssh_key} {cfg[cfg_key]}\n")
                updated_keys.add(cfg_key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    for cfg_key, ssh_key in mapping.items():
        if cfg_key in cfg and cfg_key not in updated_keys:
            new_lines.append(f"{ssh_key} {cfg[cfg_key]}\n")

    content = "".join(new_lines)
    tmp = safe_temp_file(suffix=".sshd_config", content=content)
    try:
        # Detect correct SSH service name
        ssh_service = "sshd"
        _, ssh_code = run_cmd("systemctl is-active sshd 2>/dev/null")
        if ssh_code != 0:
            _, ssh_code2 = run_cmd("systemctl is-active ssh 2>/dev/null")
            if ssh_code2 == 0:
                ssh_service = "ssh"
        _, code = run_cmd(f"sudo cp {safe_quote(tmp)} /etc/ssh/sshd_config && sudo systemctl restart {ssh_service}")
        return {"success": code == 0, "message": "SSH config updated" if code == 0 else "Failed to update SSH config"}
    finally:
        try: os.remove(tmp)
        except OSError: pass


def get_swap_info() -> Dict:
    """Get current swap status."""
    info: Dict = {"total": "0", "used": "0", "free": "0", "files": []}
    try:
        with open("/proc/swaps") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 5 and parts[0] != "Filename":
                    info["files"].append({"path": parts[0], "type": parts[1], "size_kb": parts[2], "used_kb": parts[3]})
    except Exception:
        pass
    try:
        out, _ = run_cmd("free -b | grep Swap")
        parts = out.split()
        if len(parts) >= 4:
            info["total"] = f"{int(parts[1]) / (1024**3):.1f}G"
            info["used"] = f"{int(parts[2]) / (1024**3):.1f}G"
            info["free"] = f"{int(parts[3]) / (1024**3):.1f}G"
    except Exception:
        pass
    return info


def create_swap(size: str) -> Dict:
    """Create and enable a swap file."""
    if not re.match(r'^\d+[MG]$', size.upper()):
        return {"success": False, "message": "Invalid size format. Use e.g. 2G or 512M"}
    filepath = "/swapfile"
    try:
        _, code = run_cmd(f"test -f {filepath}")
        if code == 0:
            return {"success": False, "message": f"{filepath} already exists. Remove it first."}
        if size.upper().endswith("G"):
            count = str(int(size[:-1]) * 1024)
        elif size.upper().endswith("M"):
            count = size[:-1]
        else:
            return {"success": False, "message": "Size must end with G or M"}
        out, code = run_cmd(f"sudo dd if=/dev/zero of={filepath} bs=1M count={count} status=progress", timeout=300)
        if code != 0:
            return {"success": False, "message": f"Failed to create swap file: {out}"}
        run_cmd(f"sudo chmod 600 {filepath}")
        out, code = run_cmd(f"sudo mkswap {filepath}")
        if code != 0:
            return {"success": False, "message": f"Failed to format swap: {out}"}
        out, code = run_cmd(f"sudo swapon {filepath}")
        if code != 0:
            return {"success": False, "message": f"Failed to enable swap: {out}"}
        # Add to fstab if not present
        fstab, _ = run_cmd("cat /etc/fstab")
        if filepath not in fstab:
            run_cmd(f"echo '{filepath} none swap sw 0 0' | sudo tee -a /etc/fstab")
        return {"success": True, "message": f"Swap file {filepath} ({size}) created and enabled"}
    except Exception as e:
        return {"success": False, "message": str(e)}


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
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".limits", delete=False)
    try:
        tmp.write(content)
        tmp.close()
        _, code = run_cmd(f"sudo cp {safe_quote(tmp.name)} /etc/security/limits.conf")
        return {"success": code == 0, "message": "Limits updated" if code == 0 else "Failed to update limits"}
    finally:
        try: os.remove(tmp.name)
        except OSError: pass


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


def disable_swap() -> Dict:
    """Disable all swap files."""
    out, code = run_cmd("sudo swapoff -a")
    return {"success": code == 0, "message": out or "All swap disabled"}


def get_users() -> List[Dict]:
    """List system users with login shells."""
    users = []
    try:
        with open("/etc/passwd") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 7:
                    shell = parts[6]
                    if shell and shell not in ("/usr/sbin/nologin", "/bin/false", "/sbin/nologin"):
                        users.append({"username": parts[0], "uid": int(parts[2]), "gid": int(parts[3]), "home": parts[5], "shell": shell})
    except Exception:
        pass
    return users


def add_user(username: str, password: str, groups: str = "", shell: str = "/bin/bash") -> Dict:
    """Add a new system user."""
    import subprocess
    if not re.match(r'^[a-z_][a-z0-9_-]*$', username):
        return {"success": False, "message": "Invalid username"}
    if not password or len(password) > 128:
        return {"success": False, "message": "Invalid password"}
    # Create user
    cmd = ["sudo", "useradd", "-m", "-s", shell, username]
    if groups:
        cmd = ["sudo", "useradd", "-m", "-s", shell, "-G", groups, username]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        return {"success": False, "message": f"Failed to create user: {proc.stderr.strip()}"}
    # Set password via stdin (no shell interpolation)
    proc = subprocess.run(
        ["sudo", "chpasswd"],
        input=f"{username}:{password}",
        capture_output=True, text=True, timeout=15
    )
    if proc.returncode != 0:
        return {"success": True, "message": f"User {username} created but password set failed: {proc.stderr.strip()}"}
    return {"success": True, "message": f"User {username} created"}


def delete_user(username: str) -> Dict:
    """Delete a system user."""
    if username in ("root",):
        return {"success": False, "message": "Cannot delete root"}
    out, code = run_cmd(f"sudo userdel -r {safe_quote(username)}")
    return {"success": code == 0, "message": out or f"User {username} deleted"}


def change_password(username: str, password: str) -> Dict:
    """Change user password."""
    import subprocess
    if not username or not password:
        return {"success": False, "message": "Username and password required"}
    if len(password) > 128:
        return {"success": False, "message": "Password too long"}
    proc = subprocess.run(
        ["sudo", "chpasswd"],
        input=f"{username}:{password}",
        capture_output=True, text=True, timeout=15
    )
    return {"success": proc.returncode == 0, "message": proc.stderr.strip() if proc.returncode != 0 else f"Password changed for {username}"}


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


# ── Service Optimization ──

COMMON_UNNECESSARY_SERVICES = [
    {"name": "cups", "desc": "打印服务", "safe": True, "warning": "如果有打印机或打印服务器需求请勿禁用"},
    {"name": "bluetooth", "desc": "蓝牙服务", "safe": True, "warning": "如果有蓝牙IoT设备请勿禁用"},
    {"name": "avahi-daemon", "desc": "mDNS/DNS-SD 服务", "safe": True, "warning": "如果有本地网络发现需求请勿禁用"},
    {"name": "ModemManager", "desc": "调制解调器管理", "safe": True, "warning": "如果有蜂窝网络设备请勿禁用"},
    {"name": "accounts-daemon", "desc": "用户账户服务", "safe": True, "warning": "某些桌面环境需要此服务"},
]


def get_service_optimization() -> List[Dict]:
    """Check which unnecessary services are running."""
    result = []
    for svc in COMMON_UNNECESSARY_SERVICES:
        _, code = run_cmd(f"systemctl is-enabled {svc['name']} 2>/dev/null")
        enabled = code == 0
        _, code2 = run_cmd(f"systemctl is-active {svc['name']} 2>/dev/null")
        active = code2 == 0
        result.append({**svc, "enabled": enabled, "active": active})
    return result


def optimize_services() -> List[Dict]:
    """Disable common unnecessary services for server use."""
    results = []
    for svc in COMMON_UNNECESSARY_SERVICES:
        if svc["safe"]:
            out, code = run_cmd(f"sudo systemctl disable --now {svc['name']} 2>/dev/null")
            results.append({"name": svc["name"], "success": code == 0})
    return results


# ── Quick Kernel Parameters ──

QUICK_KERNEL_PARAMS = {
    "vm.swappiness": {"desc": "Swap 倾向 (0=尽量不用, 100=积极使用)", "recommended": "10", "type": "range", "min": 0, "max": 100},
    "net.core.somaxconn": {"desc": "最大连接队列长度", "recommended": "65535", "type": "number"},
    "net.ipv4.tcp_max_syn_backlog": {"desc": "SYN 队列最大长度", "recommended": "65535", "type": "number"},
    "fs.file-max": {"desc": "系统最大文件描述符数", "recommended": "6553500", "type": "number"},
    "vm.overcommit_memory": {"desc": "内存过量分配 (0=启发式, 1=总是允许, 2=不超过swap+RAM*比率)", "recommended": "1", "type": "select", "options": ["0", "1", "2"]},
}


def get_quick_kernel_params() -> List[Dict]:
    """Get current values of common kernel params."""
    result = []
    for key, meta in QUICK_KERNEL_PARAMS.items():
        current, _ = run_cmd(f"sysctl -n {key} 2>/dev/null")
        result.append({"key": key, "current": current.strip(), **meta})
    return result


def apply_quick_kernel_params(params: Dict[str, str]) -> List[Dict]:
    """Apply kernel parameter values."""
    results = []
    for key, value in params.items():
        if key not in QUICK_KERNEL_PARAMS:
            results.append({"key": key, "success": False, "message": "Unknown parameter"})
            continue
        out, code = set_sysctl_param(key, value)
        results.append({"key": key, "success": code == 0, "message": out})
    return results


# ── 系统优化方案（场景化） ──

OPTIMIZATION_PROFILES = {
    "server": {
        "label": "服务器优化",
        "desc": "减少桌面服务开销，优化网络和内存参数，适合无头服务器环境",
        "sysctl": {
            "vm.swappiness": "10",
            "vm.vfs_cache_pressure": "50",
            "net.core.somaxconn": "65535",
            "net.core.netdev_max_backlog": "65535",
            "net.ipv4.tcp_max_syn_backlog": "8192",
            "net.ipv4.tcp_fastopen": "3",
            "fs.file-max": "6553500",
            "fs.inotify.max_user_instances": "8192",
        },
        "services_to_disable": [
            "cups", "cups-browsed", "bluetooth",
            "avahi-daemon", "ModemManager",
        ],
    },
    "desktop": {
        "label": "桌面优化",
        "desc": "保留桌面服务，优化 inotify 和虚拟内存，适合日常使用的桌面环境",
        "sysctl": {
            "vm.swappiness": "60",
            "fs.inotify.max_user_watches": "524288",
            "fs.inotify.max_user_instances": "1024",
        },
        "services_to_disable": [],
    },
}


def get_optimization_preview(profile: str) -> Dict:
    """预览某个优化方案将要变更的内容（不实际执行）。"""
    if profile not in OPTIMIZATION_PROFILES:
        return {"success": False, "message": f"Unknown profile: {profile}"}

    cfg = OPTIMIZATION_PROFILES[profile]
    sysctl_changes = []
    for key, recommended in cfg["sysctl"].items():
        current, _ = run_cmd(f"sysctl -n {key} 2>/dev/null")
        current = current.strip()
        sysctl_changes.append({
            "key": key,
            "current": current,
            "recommended": recommended,
            "will_change": current != recommended,
        })

    svc_changes = []
    for svc_name in cfg.get("services_to_disable", []):
        _, code = run_cmd(f"systemctl is-enabled {svc_name} 2>/dev/null")
        enabled = code == 0
        _, code2 = run_cmd(f"systemctl is-active {svc_name} 2>/dev/null")
        active = code2 == 0
        svc_changes.append({
            "name": svc_name,
            "enabled": enabled,
            "active": active,
            "will_disable": enabled or active,
        })

    return {
        "success": True,
        "profile": profile,
        "label": cfg["label"],
        "desc": cfg["desc"],
        "sysctl_changes": sysctl_changes,
        "svc_changes": svc_changes,
    }


def apply_optimization_profile(profile: str, sysctl_keys: Optional[List[str]] = None, svc_names: Optional[List[str]] = None) -> Dict:
    """应用某个优化方案。可指定仅应用部分项。"""
    if profile not in OPTIMIZATION_PROFILES:
        return {"success": False, "message": f"Unknown profile: {profile}"}

    cfg = OPTIMIZATION_PROFILES[profile]
    sysctl_results = []
    for key, value in cfg["sysctl"].items():
        # 如果指定了白名单，只应用白名单中的项
        if sysctl_keys is not None and key not in sysctl_keys:
            continue
        out, code = set_sysctl_param(key, value)
        sysctl_results.append({"key": key, "success": code == 0, "message": out})

    svc_results = []
    for svc_name in cfg.get("services_to_disable", []):
        if svc_names is not None and svc_name not in svc_names:
            continue
        out, code = run_cmd(f"sudo systemctl disable --now {svc_name} 2>/dev/null")
        svc_results.append({"name": svc_name, "success": code == 0})

    return {
        "success": True,
        "profile": profile,
        "sysctl_results": sysctl_results,
        "svc_results": svc_results,
    }


# ── Boot & Kernel Tuning ──

def _detect_grub_paths() -> Tuple[str, str, str]:
    """自动检测 grub 配置文件、grub.cfg 路径、mkconfig 命令。
    Returns: (defaults_file, grub_cfg_path, mkconfig_cmd)"""
    # /etc/default/grub 是标准的，几乎所有发行版都用
    defaults_file = "/etc/default/grub"

    # 检测 grub.cfg 位置和对应的 mkconfig 命令
    # UEFI 路径优先（因为更常见于现代系统）
    uefi_candidates = []
    efi_out, _ = run_cmd("ls -d /boot/efi/EFI/*/grub.cfg /boot/EFI/*/grub.cfg 2>/dev/null | head -5")
    for p in efi_out.splitlines():
        p = p.strip()
        if os.path.exists(p):
            uefi_candidates.append(p)

    # BIOS 路径
    bios_candidates = [
        "/boot/grub/grub.cfg",
        "/boot/grub2/grub.cfg",
    ]

    # 确定 mkconfig 命令
    # Debian/Ubuntu 有 update-grub 包装脚本
    # Fedora/RHEL 用 grub2-mkconfig
    # Arch/openSUSE 用 grub-mkconfig
    if os.path.exists("/usr/sbin/update-grub") or os.path.exists("/usr/bin/update-grub"):
        # Debian/Ubuntu 家族
        for cfg in uefi_candidates + bios_candidates:
            if os.path.exists(cfg):
                return defaults_file, cfg, f"update-grub"
    elif os.path.exists("/usr/sbin/grub2-mkconfig") or os.path.exists("/usr/bin/grub2-mkconfig"):
        # Fedora/RHEL 家族
        for cfg in uefi_candidates + bios_candidates:
            if os.path.exists(cfg):
                return defaults_file, cfg, f"grub2-mkconfig -o {cfg}"
    else:
        # Arch / openSUSE / 其他
        for cfg in uefi_candidates + bios_candidates:
            if os.path.exists(cfg):
                return defaults_file, cfg, f"grub-mkconfig -o {cfg}"

    # 最后兜底
    return defaults_file, "/boot/grub/grub.cfg", "grub-mkconfig -o /boot/grub/grub.cfg"


def _parse_grub_entries(grub_cfg_path: str) -> List[Dict]:
    """解析 grub.cfg 中的所有 menuentry（含子菜单）。"""
    entries = []
    if not os.path.exists(grub_cfg_path):
        return entries

    try:
        with open(grub_cfg_path, 'r', errors='ignore') as f:
            idx = 0
            for line in f:
                # 匹配 menuentry（可能有前导空白——子菜单会缩进）
                m = re.match(r"^\s*menuentry\s+'([^']+)'", line)
                if not m:
                    m = re.match(r'^\s*menuentry\s+"([^"]+)"', line)
                if not m:
                    # 有些 grub.cfg 使用 $menuentry_id_option 之类的变量
                    m = re.match(r"^\s*menuentry\s+'([^']*)", line)
                    if not m:
                        m = re.match(r'^\s*menuentry\s+"([^"]*)', line)
                if m:
                    title = m.group(1).strip()
                    if title:
                        entries.append({"index": idx, "title": title})
                        idx += 1
    except Exception:
        pass

    return entries


def get_grub_config() -> Dict:
    """读取当前 GRUB 配置。"""
    defaults_file, grub_cfg_path, mkconfig_cmd = _detect_grub_paths()

    config = {
        "default": "",
        "timeout": "",
        "cmdline": "",
        "entries": [],
        "config_file": defaults_file,
        "grub_cfg_path": grub_cfg_path,
        "mkconfig_cmd": mkconfig_cmd,
    }
    # 读 /etc/default/grub
    try:
        with open(defaults_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GRUB_DEFAULT="):
                    config["default"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("GRUB_TIMEOUT="):
                    config["timeout"] = line.split("=", 1)[1].strip()
                elif line.startswith("GRUB_CMDLINE_LINUX="):
                    config["cmdline"] = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass

    # 解析 grub.cfg 中的内核条目
    config["entries"] = _parse_grub_entries(grub_cfg_path)

    # 如果没有 grub 条目，尝试 systemd-boot
    if not config["entries"]:
        out2, _ = run_cmd("ls /boot/loader/entries/*.conf 2>/dev/null | head -20")
        if out2:
            for f in out2.splitlines():
                f = f.strip()
                title_out, _ = run_cmd(f"grep '^title' {f} 2>/dev/null | head -1")
                if title_out:
                    config["entries"].append({
                        "index": len(config["entries"]),
                        "title": title_out.split("title", 1)[-1].strip(),
                        "file": f,
                    })
    return config


def _rewrite_grub_defaults(updates: Dict[str, str], remove_keys: List[str] = None) -> Tuple[str, int]:
    """安全地重写 /etc/default/grub：读取 → 修改 → 写临时文件 → sudo cp → mkconfig。
    避免 shell 注入风险。"""
    defaults_file, grub_cfg_path, mkconfig_cmd = _detect_grub_paths()

    # 读取当前内容
    lines = []
    try:
        with open(defaults_file) as f:
            lines = f.readlines()
    except Exception:
        pass

    # 应用修改
    remove_set = set(remove_keys or [])
    new_lines = []
    seen_keys = set()
    for line in lines:
        stripped = line.strip()
        matched = False
        for key, value in updates.items():
            if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
                if key not in remove_set:
                    new_lines.append(f'{key}="{value}"\n')
                seen_keys.add(key)
                matched = True
                break
        if not matched:
            # 检查是否是需要移除的 key
            skip = False
            for rk in remove_set:
                if stripped.startswith(f"{rk}=") or stripped.startswith(f"#{rk}="):
                    skip = True
                    break
            if not skip:
                new_lines.append(line)

    # 追加未出现的新 key
    for key, value in updates.items():
        if key not in seen_keys and key not in remove_set:
            new_lines.append(f'{key}="{value}"\n')

    # 写入临时文件
    tmp = safe_temp_file(suffix=".grub", content="".join(new_lines))
    out, code = run_cmd(
        f"sudo cp {safe_quote(tmp)} {safe_quote(defaults_file)} && sudo {mkconfig_cmd}",
        timeout=30
    )
    os.remove(tmp)
    return out.strip(), code


def set_grub_default(value: str) -> Tuple[str, int]:
    """设置默认启动内核。value: 'saved' / 数字 / 内核标题。"""
    safe_val = value.strip()
    updates = {}
    remove = []

    if safe_val == "saved":
        updates["GRUB_DEFAULT"] = "saved"
        updates["GRUB_SAVEDEFAULT"] = "true"
    elif safe_val.isdigit():
        updates["GRUB_DEFAULT"] = safe_val
        remove.append("GRUB_SAVEDEFAULT")
    else:
        updates["GRUB_DEFAULT"] = safe_val
        remove.append("GRUB_SAVEDEFAULT")

    return _rewrite_grub_defaults(updates, remove)


def set_grub_cmdline(params: str) -> Tuple[str, int]:
    """设置 GRUB 内核引导参数。"""
    return _rewrite_grub_defaults({"GRUB_CMDLINE_LINUX": params.strip()})


# ── CPU 频率调节器 ──

def get_cpu_governor() -> Dict:
    """获取 CPU 频率调节器状态。"""
    result = {
        "available": [],
        "current": "",
        "driver": "",
    }
    # 从 sysfs 读取
    out, _ = run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null")
    if out:
        result["available"] = [g.strip() for g in out.split()]
    out2, _ = run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null")
    if out2:
        result["current"] = out2.strip()
    out3, _ = run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>/dev/null")
    if out3:
        result["driver"] = out3.strip()
    # 备选：cpupower
    if not result["current"]:
        out4, _ = run_cmd("cpupower frequency-info -p 2>/dev/null | grep 'current'")
        if out4:
            result["current"] = out4.split()[-1].strip()
    return result


def set_cpu_governor(governor: str) -> Tuple[bool, str]:
    """设置所有 CPU 的频率调节器。"""
    valid = {"performance", "powersave", "ondemand", "conservative", "schedutil", "userspace"}
    g = governor.strip().lower()
    if g not in valid:
        return False, f"Invalid governor: {governor}. Valid: {', '.join(sorted(valid))}"
    out, code = run_cmd(f"sudo cpupower frequency-set -g {g} 2>&1", timeout=15)
    if code != 0:
        # fallback: sysfs
        for cpu_path in ["/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"]:
            out2, code2 = run_cmd(
                f"echo {shlex.quote(g)} | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>&1",
                timeout=10
            )
            if code2 == 0:
                return True, f"已设置 governor={g} (via sysfs)"
        return False, out.strip()
    return True, out.strip()


# ── I/O 调度器 ──

def get_io_scheduler() -> Dict:
    """获取所有块设备的 I/O 调度器。"""
    result = {"devices": []}
    out, _ = run_cmd("ls /sys/block/ 2>/dev/null")
    for dev in out.splitlines():
        dev = dev.strip()
        if not dev or dev.startswith("loop") or dev.startswith("ram"):
            continue
        sched_out, _ = run_cmd(f"cat /sys/block/{dev}/queue/scheduler 2>/dev/null")
        if sched_out:
            # 格式: [mq-deadline] kyber none
            current = ""
            available = []
            for s in sched_out.strip().split():
                if s.startswith("[") and s.endswith("]"):
                    current = s[1:-1]
                    available.append(current)
                else:
                    available.append(s)
            result["devices"].append({
                "name": dev,
                "current": current,
                "available": available,
            })
    return result


def set_io_scheduler(device: str, scheduler: str) -> Tuple[bool, str]:
    """设置指定块设备的 I/O 调度器。"""
    if not device or "/" in device or ".." in device:
        return False, "Invalid device name"
    sched_path = f"/sys/block/{device}/queue/scheduler"
    out, code = run_cmd(
        f"echo {shlex.quote(scheduler)} | sudo tee {sched_path} 2>&1",
        timeout=10
    )
    if code != 0:
        return False, out.strip()
    return True, f"已设置 {device} scheduler={scheduler}"


# ── 常用引导参数预设 ──

BOOT_PARAM_PRESETS = {
    "quiet_boot": {
        "label": "静默启动",
        "params": "quiet splash",
        "desc": "隐藏内核日志，显示启动画面",
    },
    "verbose_boot": {
        "label": "详细启动",
        "params": "",
        "desc": "显示所有内核日志（移除 quiet splash）",
    },
    "performance": {
        "label": "性能优化",
        "params": "mitigations=off transparent_hugepage=always elevator=mq-deadline",
        "desc": "禁用 CPU 漏洞缓解 + 透明大页 + mq-deadline",
    },
    "virtualization": {
        "label": "虚拟化主机",
        "params": "intel_iommu=on amd_iommu=on iommu=pt kvm.ignore_msrs=1 vfio-pci.ids=",
        "desc": "启用 IOMMU + KVM + VFIO（需根据硬件调整 vfio-pci.ids）",
    },
    "security": {
        "label": "安全加固",
        "params": "mitigations=auto lockdown=confidentiality module.sig_enforce=1",
        "desc": "启用所有 CPU 漏洞缓解 + 内核锁定 + 模块签名",
    },
    "low_latency": {
        "label": "低延迟",
        "params": "preempt=full nohz=on rcu_nocbs=all idle=poll",
        "desc": "完全抢占内核 + 无滴答 + RCU 隔离（实时场景）",
    },
}
