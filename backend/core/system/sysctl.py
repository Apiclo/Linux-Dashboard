"""System parameters: hostname, timezone, locale, sysctl, hosts, SSH, swap."""
import os
import re
import psutil
import platform
import socket
from typing import Dict, List, Tuple, Optional
from utils.helpers import run_cmd, safe_quote, validate_hostname, atomic_sudo_write


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
    # Timezone — prefer timedatectl, fallback to /etc/localtime symlink
    tz, tz_code = run_cmd("timedatectl show --property=Timezone --value 2>/dev/null")
    if tz_code == 0 and tz:
        info["timezone"] = tz
    else:
        lt_out, _ = run_cmd("readlink -f /etc/localtime 2>/dev/null")
        if lt_out and "zoneinfo" in lt_out:
            info["timezone"] = lt_out.split("zoneinfo/")[-1]
        else:
            info["timezone"] = "Unknown"

    loc, _ = run_cmd("locale | grep LANG=")
    info["locale"] = loc.split("=")[-1].strip('"') if loc else "Unknown"
    return info


def get_timezone_list():
    out, code = run_cmd("timedatectl list-timezones 2>/dev/null")
    if code == 0 and out:
        return out.splitlines()
    # Fallback: list zoneinfo files
    out2, _ = run_cmd(
        "find /usr/share/zoneinfo -type f 2>/dev/null | "
        "sed 's|/usr/share/zoneinfo/||' | grep -v '^right/' | sort"
    )
    return out2.splitlines() if out2 else ["UTC"]


def get_locale_list():
    out, _ = run_cmd("locale -a 2>/dev/null")
    return sorted(out.splitlines()) if out else ["en_US.UTF-8"]


def set_hostname(name: str) -> Tuple[str, int]:
    """Set system hostname.  Uses hostnamectl (systemd) or hostname cmd + /etc/hostname."""
    if not validate_hostname(name):
        return "Invalid hostname", -1

    # Try hostnamectl first
    _, code = run_cmd(f"sudo hostnamectl set-hostname {safe_quote(name)} 2>/dev/null")
    if code == 0:
        return "Hostname set", 0

    # Fallback: direct write + hostname command
    from utils.shell import atomic_sudo_write as _asw
    ok, msg = _asw("/etc/hostname", name + "\n")
    if not ok:
        return msg, -1
    return run_cmd(f"sudo hostname {safe_quote(name)} 2>&1")


def set_timezone(tz: str) -> Tuple[str, int]:
    """Set system timezone.  Uses timedatectl or symlinks /etc/localtime."""
    _, code = run_cmd(f"sudo timedatectl set-timezone {safe_quote(tz)} 2>/dev/null")
    if code == 0:
        return "Timezone set", 0

    # Fallback: symlink /etc/localtime (works on all Linux systems)
    tz_path = f"/usr/share/zoneinfo/{tz}"
    if not os.path.exists(tz_path):
        return f"Timezone not found: {tz}", -1
    out, code = run_cmd(
        f"sudo ln -sf {safe_quote(tz_path)} /etc/localtime 2>&1",
        timeout=10
    )
    # Also write /etc/timezone for Debian compatibility
    if code == 0:
        run_cmd(f"echo {safe_quote(tz)} | sudo tee /etc/timezone >/dev/null 2>&1")
    return out, code


def set_locale(loc: str) -> Tuple[str, int]:
    """Set system locale.  Uses localectl or writes locale config files."""
    _, code = run_cmd(f"sudo localectl set-locale LANG={safe_quote(loc)} 2>/dev/null")
    if code == 0:
        return "Locale set", 0

    # Fallback: write to distribution-specific locale config
    for conf in ["/etc/locale.conf", "/etc/default/locale"]:
        try:
            from utils.shell import atomic_sudo_write as _asw
            ok, msg = _asw(conf, f'LANG="{loc}"\n')
            if ok:
                return f"Locale written to {conf}", 0
        except Exception:
            continue
    return "Failed to set locale — no supported method found", -1


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
    ok, _ = atomic_sudo_write('/etc/hosts', content)
    return ok


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
    post_cmd = 'sudo systemctl restart sshd || sudo systemctl restart ssh'
    ok, msg = atomic_sudo_write('/etc/ssh/sshd_config', content, post_cmd=post_cmd)
    return {"success": ok, "message": "SSH config updated" if ok else f"Failed to update SSH config: {msg}"}


def get_swap_info() -> Dict:
    """获取 Swap 状态（locale 无关，适用于所有发行版）。"""
    info: Dict = {"total": "0", "used": "0", "free": "0", "files": []}

    # 1. 从 /proc/swaps 读取详细信息
    try:
        with open("/proc/swaps") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 5 and parts[0] != "Filename":
                    info["files"].append({
                        "path": parts[0], "type": parts[1],
                        "size_kb": parts[2], "used_kb": parts[3],
                        "priority": parts[4],
                    })
    except Exception:
        pass

    # 2. 从 /proc/meminfo 读取总量（locale 无关）
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("SwapTotal:"):
                    kb = int(line.split()[1])
                    info["total"] = f"{kb / (1024**2):.1f}G" if kb > 0 else "0"
                elif line.startswith("SwapFree:"):
                    kb_free = int(line.split()[1])
                    info["free"] = f"{kb_free / (1024**2):.1f}G" if kb_free > 0 else "0"
        # 计算已用
        if info["total"] != "0":
            total_kb = float(info["total"].replace("G", "")) * 1024**2
            free_kb = float(info["free"].replace("G", "")) * 1024**2
            info["used"] = f"{(total_kb - free_kb) / (1024**2):.1f}G"
    except Exception:
        pass

    # 3. swapon --show 作为补充（如果 /proc/swaps 为空）
    if not info["files"]:
        try:
            out, code = run_cmd("LC_ALL=C swapon --show --noheadings 2>/dev/null")
            if code == 0 and out.strip():
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        info["files"].append({
                            "path": parts[0], "type": parts[1],
                            "size_kb": parts[2], "used_kb": parts[3],
                            "priority": parts[4] if len(parts) > 4 else "0",
                        })
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


def disable_swap() -> Dict:
    """Disable all swap files."""
    out, code = run_cmd("sudo swapoff -a")
    return {"success": code == 0, "message": out or "All swap disabled"}


def persist_sysctl(key: str, value: str) -> Tuple[str, int]:
    """将 sysctl 参数持久化到 /etc/sysctl.d/99-tuxtacklebox.conf。"""
    conf_dir = "/etc/sysctl.d"
    conf_file = os.path.join(conf_dir, "99-tuxtacklebox.conf")
    os.makedirs(conf_dir, exist_ok=True)

    # 读现有配置
    lines = []
    found = False
    try:
        with open(conf_file) as f:
            lines = f.readlines()
    except FileNotFoundError:
        pass

    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}=") or line.strip().startswith(f"#{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")

    ok, msg = atomic_sudo_write(conf_file, "".join(new_lines), post_cmd=f'sudo sysctl -p {safe_quote(conf_file)}')
    return msg.strip(), 0 if ok else -1


# ── 诊断报告 ──

def generate_diagnostic_report() -> str:
    """Generate a Markdown diagnostic report of the system."""
    info = get_system_info()
    distro = {}
    try:
        from core.distro import detect_distro
        distro = detect_distro()
    except Exception:
        pass

    lines = [
        f"# TuxTackleBox 诊断报告",
        f"**生成时间:** {info.get('uptime', 'N/A')}",
        f"",
        f"## 系统概览",
        f"- **OS:** {info.get('os_name', 'N/A')}",
        f"- **内核:** {info.get('kernel', 'N/A')}",
        f"- **架构:** {info.get('arch', 'N/A')}",
        f"- **CPU:** {info.get('cpu', 'N/A')} ({info.get('cpu_cores', 0)}C/{info.get('cpu_threads', 0)}T)",
        f"- **内存:** {info.get('ram_used_gb', 0)}/{info.get('ram_total_gb', 0)} GB ({info.get('ram_percent', 0)}%)",
        f"- **磁盘:** {info.get('disk_used_gb', 0)}/{info.get('disk_total_gb', 0)} GB ({info.get('disk_percent', 0)}%)",
        f"- **运行时间:** {info.get('uptime', 'N/A')}",
        f"- **时区:** {info.get('timezone', 'N/A')}",
        f"- **桌面:** {info.get('desktop', 'N/A')}",
        f"- **发行版:** {distro.get('pretty_name', 'N/A')} ({distro.get('pkg_manager', 'N/A')})",
        f"",
        f"## 磁盘使用",
    ]

    df, _ = run_cmd("df -h -x tmpfs -x devtmpfs -x efivarfs 2>/dev/null | tail -n +2")
    for line in df.splitlines():
        parts = line.split()
        if len(parts) >= 6:
            lines.append(f"- `{parts[0]}` → {parts[5]} ({parts[4]} used, {parts[2]} avail)")

    lines += ["", "## 内存", f"```"]
    mem, _ = run_cmd("free -h 2>/dev/null")
    lines.append(mem)
    lines += ["```", "", "## 网络接口", f"```"]
    ip, _ = run_cmd("ip -br addr 2>/dev/null")
    lines.append(ip)
    lines += ["```", "", "## 最近系统日志 (journalctl)", f"```"]
    logs, _ = run_cmd("journalctl -n 30 --no-pager 2>/dev/null | tail -30")
    lines.append(logs)
    lines += ["```", "", "## 关键内核参数", f"```"]
    sysctl_out, _ = run_cmd("sysctl vm.swappiness kernel.hostname net.ipv4.ip_forward 2>/dev/null")
    lines.append(sysctl_out)
    lines += ["```"]

    return "\n".join(lines)


def check_available_features() -> Dict:
    """Detect which subsystems / tools are available on this host."""
    import os as _os
    def _has(cmd): _, c = run_cmd(f"which {cmd} 2>/dev/null"); return c == 0
    def _has_systemd(): return _os.path.isdir("/run/systemd/system")
    def _has_openrc(): return _os.path.exists("/sbin/openrc") or _os.path.exists("/usr/sbin/openrc")
    def _svc_active(svc): _, c = run_cmd(f"systemctl is-active --quiet {svc} 2>/dev/null"); return c == 0

    pm = "unknown"
    try:
        from core.distro import detect_distro
        pm = detect_distro().get("pkg_manager", "unknown")
    except Exception: pass

    return {
        "init_system": "systemd" if _has_systemd() else ("openrc" if _has_openrc() else "sysv"),
        "package_manager": pm,
        "firewall": (
            "ufw" if _has("ufw") and _svc_active("ufw") else
            ("firewalld" if _has("firewall-cmd") and _svc_active("firewalld") else
             ("nftables" if _has("nft") else "none"))
        ),
        "sudo": _os.geteuid() == 0 or _has("sudo"),
        "lvm": _has("lvm"),
        "btrfs": _has("btrfs"),
        "zfs": _has("zpool"),
        "smartctl": _has("smartctl"),
        "cryptsetup": _has("cryptsetup"),
        "mdadm": _has("mdadm"),
        "sshfs": _has("sshfs"),
        "gcc": _has("gcc"),
        "nvidia_smi": _has("nvidia-smi"),
        "rocm_smi": _has("rocm-smi"),
        "isoinfo": _has("isoinfo"),
        "auditd": _svc_active("auditd"),
        "pam": _os.path.exists("/etc/pam.d"),
        "selinux": _os.path.exists("/etc/selinux/config"),
        "apparmor": _os.path.exists("/etc/apparmor.d"),
        "netplan": _os.path.exists("/etc/netplan"),
        "nmcli": _has("nmcli"),
        "snap": _has("snap"),
        "flatpak": _has("flatpak"),
        "chroot": _os.path.exists("/usr/sbin/chroot") or _os.path.exists("/usr/bin/chroot"),
    }


def get_thermal() -> Dict:
    """获取 CPU 温度和风扇转速。"""
    result: Dict = {"cpu_temp": None, "fans": []}

    # Try /sys/class/thermal
    for i in range(10):
        tfile = f"/sys/class/thermal/thermal_zone{i}/temp"
        ttype = ""
        try:
            with open(f"/sys/class/thermal/thermal_zone{i}/type") as f:
                ttype = f.read().strip()
        except Exception:
            pass
        if ttype in ("x86_pkg_temp", "cpu-thermal", "acpitz"):
            try:
                with open(tfile) as f:
                    raw = int(f.read().strip())
                    result["cpu_temp"] = raw / 1000.0
            except Exception:
                pass

    # Try lm-sensors as fallback
    if not result["cpu_temp"]:
        import json as _json
        out, _ = run_cmd("sensors -j 2>/dev/null")
        try:
            data = _json.loads(out)
            for chip_name, chip_data in data.items():
                if "coretemp" in chip_name.lower() or "k10temp" in chip_name.lower() or "cpu_thermal" in chip_name.lower():
                    for key, val in chip_data.items():
                        if isinstance(val, dict):
                            if "temp1_input" in val and not result["cpu_temp"]:
                                result["cpu_temp"] = val["temp1_input"]
                            for k, v in val.items():
                                if "fan" in k and "input" in k:
                                    result["fans"].append({"name": f"{chip_name}/{key}/{k}", "rpm": v})
        except Exception:
            pass

    return result


def get_notifications() -> Dict:
    """获取最近 3 条系统事件（journalctl -p 3）。"""
    out, _ = run_cmd("journalctl -p 3 -n 3 --no-pager -o short 2>/dev/null")
    events = [line.strip() for line in out.splitlines() if line.strip()]
    return {"events": events}


def get_cpu_freq_details() -> Dict:
    """获取每个 CPU 核心的频率详情（当前/最小/最大频率，驱动，调控器）。"""
    result: Dict = {"cores": [], "driver": "", "governor": "", "boost": False}

    # Governor and driver
    gov_out, _ = run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null")
    result["governor"] = gov_out.strip()
    drv_out, _ = run_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>/dev/null")
    result["driver"] = drv_out.strip()

    # Boost status (Intel turbo / AMD Core Performance Boost)
    boost_paths = [
        "/sys/devices/system/cpu/intel_pstate/no_turbo",
        "/sys/devices/system/cpu/cpufreq/boost",
    ]
    for bp in boost_paths:
        try:
            with open(bp) as f:
                val = f.read().strip()
                result["boost"] = val == "0" or val == "1"
                break
        except Exception:
            pass

    # Per-core frequency
    cpu_dirs = sorted([d for d in os.listdir("/sys/devices/system/cpu") if re.match(r'cpu\d+$', d)])
    for cpu in cpu_dirs[:32]:  # Max 32 cores
        base = f"/sys/devices/system/cpu/{cpu}/cpufreq"
        info: Dict = {"core": cpu.replace("cpu", "")}
        for fname, key in [
            ("scaling_cur_freq", "cur_khz"),
            ("scaling_min_freq", "min_khz"),
            ("scaling_max_freq", "max_khz"),
            ("cpuinfo_min_freq", "hw_min_khz"),
            ("cpuinfo_max_freq", "hw_max_khz"),
        ]:
            try:
                with open(f"{base}/{fname}") as f:
                    val = f.read().strip()
                    info[key] = int(val) if val.isdigit() else val
            except Exception:
                info[key] = None
        result["cores"].append(info)

    return result
