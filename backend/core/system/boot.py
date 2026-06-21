"""Boot configuration: GRUB, kernel cmdline, CPU governor, I/O scheduler, initramfs, SELinux."""
import os
import re
import shlex
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote, atomic_sudo_write
from core.gpu import INITRAMFS_CMDS


def _detect_all_bootloaders() -> List[str]:
    """检测系统上所有已安装的引导加载器。返回列表如 ['grub', 'systemd-boot', 'refind']。"""
    found = []

    # systemd-boot
    if os.path.isdir("/boot/loader/entries"):
        entries = [f for f in os.listdir("/boot/loader/entries") if f.endswith(".conf")]
        if entries:
            found.append("systemd-boot")
    if "systemd-boot" not in found:
        for efi_dir in ("/boot/efi/loader", "/boot/EFI/loader", "/efi/loader"):
            if os.path.isdir(efi_dir) and os.path.isdir(os.path.join(efi_dir, "entries")):
                if os.path.exists(os.path.join(efi_dir, "entries")) and os.listdir(os.path.join(efi_dir, "entries")):
                    found.append("systemd-boot")
                    break

    # GRUB
    for cfg in ("/boot/grub/grub.cfg", "/boot/grub2/grub.cfg"):
        if os.path.exists(cfg):
            found.append("grub")
            break
    if "grub" not in found:
        efi_out, _ = run_cmd("ls -d /boot/efi/EFI/*/grub.cfg /boot/EFI/*/grub.cfg 2>/dev/null | head -1")
        if efi_out.strip() and os.path.exists(efi_out.strip()):
            found.append("grub")

    # rEFInd
    for refind_dir in ("/boot/efi/EFI/refind", "/boot/EFI/refind", "/boot/refind"):
        if os.path.isdir(refind_dir) and os.path.isfile(os.path.join(refind_dir, "refind.conf")):
            found.append("refind")
            break

    return found if found else ["unknown"]


def _detect_bootloader() -> str:
    """Detect the primary bootloader. Returns the first one found."""
    all_bl = _detect_all_bootloaders()
    return all_bl[0] if all_bl else "unknown"


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


def _find_loader_entries_dir() -> str:
    """Find the systemd-boot loader entries directory, or empty string."""
    candidates = [
        "/boot/loader/entries",
        "/boot/efi/loader/entries",
        "/boot/EFI/loader/entries",
        "/efi/loader/entries",
    ]
    for d in candidates:
        if os.path.isdir(d):
            return d
    return ""


def _list_systemd_boot_entries() -> List[Dict]:
    """Parse /boot/loader/entries/*.conf files for systemd-boot entries.

    Each .conf file has fields like:
        title   <name>
        linux   /vmlinuz-...
        initrd  /initramfs-...
        options <kernel cmdline>

    Returns a list of dicts with keys: index, title, linux, initrd, options, file.
    """
    entries = []
    entries_dir = _find_loader_entries_dir()
    if not entries_dir:
        return entries

    try:
        idx = 0
        for fname in sorted(os.listdir(entries_dir)):
            if not fname.endswith(".conf"):
                continue
            fpath = os.path.join(entries_dir, fname)
            entry: Dict = {"index": idx, "title": "", "linux": "", "initrd": "",
                           "options": "", "file": fpath}
            try:
                with open(fpath, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("title "):
                            entry["title"] = line.split(" ", 1)[1].strip()
                        elif line.startswith("linux "):
                            entry["linux"] = line.split(" ", 1)[1].strip()
                        elif line.startswith("initrd "):
                            entry["initrd"] = line.split(" ", 1)[1].strip()
                        elif line.startswith("options "):
                            entry["options"] = line.split(" ", 1)[1].strip()
            except Exception:
                pass

            if entry["title"]:
                entries.append(entry)
                idx += 1
    except Exception:
        pass

    return entries


def _find_refind_conf() -> str:
    """Find rEFInd configuration file path."""
    for d in ("/boot/efi/EFI/refind", "/boot/EFI/refind", "/boot/refind"):
        p = os.path.join(d, "refind.conf")
        if os.path.isfile(p):
            return p
    return ""


def _parse_refind_entries() -> List[Dict]:
    """Parse rEFInd menu entries from refind.conf and detected OS stanzas."""
    entries = []
    conf = _find_refind_conf()
    if not conf:
        return entries
    idx = 0
    # rEFInd auto-detects kernels; we can list them from /boot
    import glob as _glob
    for pattern in ("/boot/vmlinuz-*", "/boot/vmlinuz*", "/boot/EFI/*/vmlinuz*"):
        for k in sorted(_glob.glob(pattern)):
            name = os.path.basename(k)
            entries.append({"index": idx, "title": name, "linux": k, "initrd": "", "options": ""})
            idx += 1
    # Also parse manual stanzas from refind.conf
    if os.path.isfile(conf):
        try:
            with open(conf) as f:
                current = None
                for line in f:
                    line = line.strip()
                    if line.startswith("menuentry "):
                        if current:
                            entries.append(current)
                        current = {"index": idx, "title": line.split('"')[1] if '"' in line else line[10:].strip(), "linux": "", "initrd": "", "options": ""}
                        idx += 1
                    elif current and line.startswith("loader "):
                        current["linux"] = line.split(" ", 1)[1].strip()
                    elif current and line.startswith("initrd "):
                        current["initrd"] = line.split(" ", 1)[1].strip()
                    elif current and line.startswith("options "):
                        current["options"] = line.split(" ", 1)[1].strip()
                if current:
                    entries.append(current)
        except Exception:
            pass
    return entries


def _get_refind_conf() -> Dict:
    """Get rEFInd configuration from refind.conf."""
    result: Dict = {"default": "", "timeout": "20"}
    conf = _find_refind_conf()
    if not conf:
        return result
    try:
        with open(conf) as f:
            for line in f:
                line = line.strip()
                if line.startswith("timeout "):
                    result["timeout"] = line.split(" ", 1)[1].strip()
                elif line.startswith("default_selection "):
                    result["default"] = line.split(" ", 1)[1].strip().strip('"')
    except Exception:
        pass
    return result


def _get_refind_config(config: Dict) -> Dict:
    """Fill config dict with rEFInd boot entries."""
    rc = _get_refind_conf()
    config["default"] = rc["default"]
    config["timeout"] = rc["timeout"]
    config["entries"] = _parse_refind_entries()
    config["config_file"] = _find_refind_conf()
    if config["entries"] and config["entries"][0].get("options"):
        config["cmdline"] = config["entries"][0]["options"]
    return config


def _set_systemd_boot_default(title: str) -> Tuple[str, int]:
    """Set the default systemd-boot entry by title.

    Modifies (or creates) /boot/loader/loader.conf with:
        default <title>

    Also copies the matching entry .conf to a well-known name pattern.
    """
    entries_dir = _find_loader_entries_dir()
    if not entries_dir:
        return "systemd-boot entries directory not found", -1

    # Find the loader.conf (one level up from entries/)
    loader_dir = os.path.dirname(entries_dir)
    loader_conf = os.path.join(loader_dir, "loader.conf")

    # Read existing loader.conf
    lines = []
    try:
        with open(loader_conf, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        pass

    # Update or add 'default' key
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("default "):
            new_lines.append(f"default {title}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"default {title}\n")

    # Write loader.conf atomically
    ok, msg = atomic_sudo_write(loader_conf, "".join(new_lines))
    if not ok:
        return msg, -1

    return f"Systemd-boot default set to: {title}", 0


def _set_systemd_boot_cmdline(params: str) -> Tuple[str, int]:
    """Add kernel command-line parameters to all systemd-boot entries.

    For each entry .conf file, adds the given params to the 'options' line.
    Existing options are preserved; params are appended.

    Args:
        params: Space-separated kernel command-line parameters.

    Returns:
        (message, exit_code) tuple.
    """
    entries_dir = _find_loader_entries_dir()
    if not entries_dir:
        return "systemd-boot entries directory not found", -1

    if not os.path.isdir(entries_dir):
        return f"Entries directory not accessible: {entries_dir}", -1

    updated = 0
    for fname in sorted(os.listdir(entries_dir)):
        if not fname.endswith(".conf"):
            continue
        fpath = os.path.join(entries_dir, fname)

        try:
            with open(fpath, 'r') as f:
                content = f.read()
        except Exception:
            continue

        # Update options line: replace existing or append after linux/initrd
        if re.search(r'^options\s+', content, re.MULTILINE):
            new_content = re.sub(
                r'^(options\s+.*)$',
                rf'\1 {params}',
                content,
                flags=re.MULTILINE
            )
        else:
            # Insert options line after the last linux/initrd line
            new_content = re.sub(
                r'(\n)(?!.*\n(?:options|linux|initrd)\s)',
                rf'\1options {params}\n',
                content,
                count=1
            )

        if new_content != content:
            ok, msg = atomic_sudo_write(fpath, new_content)
            if ok:
                updated += 1

    if updated == 0:
        return "No systemd-boot entries were updated", -1
    return f"Updated cmdline for {updated} systemd-boot entr{'y' if updated == 1 else 'ies'}", 0


def _get_loader_conf() -> Dict:
    """Read systemd-boot loader.conf and return default/timeout values."""
    entries_dir = _find_loader_entries_dir()
    loader_dir = os.path.dirname(entries_dir) if entries_dir else ""
    loader_conf = os.path.join(loader_dir, "loader.conf") if loader_dir else ""

    conf = {"default": "", "timeout": ""}
    if not loader_conf or not os.path.exists(loader_conf):
        return conf

    try:
        with open(loader_conf, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("default "):
                    conf["default"] = line.split(" ", 1)[1].strip()
                elif line.startswith("timeout "):
                    conf["timeout"] = line.split(" ", 1)[1].strip()
    except Exception:
        pass
    return conf


def get_grub_config(bootloader: str = "") -> Dict:
    """Read boot configuration for specified bootloader (or auto-detect).

    Args:
        bootloader: 'grub', 'systemd-boot', 'refind', or '' for auto-detect.

    Returns a dict with:
        bootloader      – the active bootloader
        available       – list of all detected bootloaders
        default         – default entry identifier
        timeout         – boot timeout in seconds
        cmdline         – kernel command-line parameters
        entries         – list of boot entries [{index, title, ...}]
        config_file     – path to the main config file
    """
    available = _detect_all_bootloaders()
    bl = bootloader.strip() if bootloader else (available[0] if available else "unknown")

    config: Dict = {
        "bootloader": bl,
        "available": available,
        "default": "",
        "timeout": "",
        "cmdline": "",
        "entries": [],
        "config_file": "",
        "grub_cfg_path": "",
        "mkconfig_cmd": "",
    }

    if bl == "systemd-boot":
        lconf = _get_loader_conf()
        config["default"] = lconf["default"]
        config["timeout"] = lconf["timeout"]
        config["entries"] = _list_systemd_boot_entries()
        for e in config["entries"]:
            if e.get("options"):
                config["cmdline"] = e["options"]
                break
        entries_dir = _find_loader_entries_dir()
        loader_dir = os.path.dirname(entries_dir) if entries_dir else ""
        config["config_file"] = os.path.join(loader_dir, "loader.conf") if loader_dir else ""
        return config

    if bl == "refind":
        return _get_refind_config(config)

    # ── GRUB path (default) ──
    defaults_file, grub_cfg_path, mkconfig_cmd = _detect_grub_paths()
    config["config_file"] = defaults_file
    config["grub_cfg_path"] = grub_cfg_path
    config["mkconfig_cmd"] = mkconfig_cmd

    # Read /etc/default/grub
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

    # Parse grub.cfg menu entries
    config["entries"] = _parse_grub_entries(grub_cfg_path)

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

    # 原子写入配置文件
    ok, msg = atomic_sudo_write(defaults_file, "".join(new_lines), post_cmd=f'sudo {mkconfig_cmd}')
    return msg.strip(), 0 if ok else -1


def set_grub_default(value: str) -> Tuple[str, int]:
    """Set the default boot entry. Auto-dispatches to systemd-boot or GRUB.

    For GRUB: value can be 'saved', a numeric index, or a menuentry title.
    For systemd-boot: value is the title of the entry.
    """
    bl = _detect_bootloader()

    if bl == "systemd-boot":
        return _set_systemd_boot_default(value.strip())

    # ── GRUB path ──
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
    """Set kernel command-line parameters. Dispatches to systemd-boot or GRUB."""
    bl = _detect_bootloader()

    if bl == "systemd-boot":
        return _set_systemd_boot_cmdline(params.strip())

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


# ── Grub 修复 ──

def repair_grub(target_disk: str = "", target_root: str = "") -> Tuple[str, int]:
    """一键修复 GRUB 引导。"""
    _, grub_cfg, mkconfig = _detect_grub_paths()
    cmds = []

    if target_root:
        # chroot 方式修复
        cmds.extend([
            f"sudo mount --bind /dev {safe_quote(target_root)}/dev 2>/dev/null",
            f"sudo mount --bind /proc {safe_quote(target_root)}/proc 2>/dev/null",
            f"sudo mount --bind /sys {safe_quote(target_root)}/sys 2>/dev/null",
        ])
        if target_disk:
            cmds.append(f"sudo chroot {safe_quote(target_root)} grub-install {safe_quote(target_disk)} 2>&1")
        cmds.append(f"sudo chroot {safe_quote(target_root)} {mkconfig.split()[-1]} 2>&1")
        cmds.extend([
            f"sudo umount {safe_quote(target_root)}/dev 2>/dev/null",
            f"sudo umount {safe_quote(target_root)}/proc 2>/dev/null",
            f"sudo umount {safe_quote(target_root)}/sys 2>/dev/null",
        ])
    else:
        # 本机修复
        if target_disk:
            cmds.append(f"sudo grub-install {safe_quote(target_disk)} 2>&1")
        cmds.append(f"sudo {mkconfig} 2>&1")

    out, code = run_cmd(" && ".join(cmds), timeout=60)
    return out.strip(), code


# ── initramfs 重建 ──

def rebuild_initramfs(all_kernels: bool = True) -> str:
    """重建 initramfs。自动检测发行版使用的工具。"""
    from core.distro import detect_distro
    pm = detect_distro()["pkg_manager"]
    base = INITRAMFS_CMDS.get(pm)
    if not base:
        return "echo 'No supported initramfs tool found (mkinitcpio/dracut/update-initramfs)'"

    if 'mkinitcpio' in base:
        if all_kernels:
            return f"{base} 2>&1"
        return "sudo mkinitcpio -p linux 2>&1"
    elif 'dracut' in base:
        if all_kernels:
            return "sudo dracut --regenerate-all --force 2>&1"
        kver_out, _ = run_cmd("uname -r")
        return f"sudo dracut --force --kver {kver_out.strip()} 2>&1"
    elif 'update-initramfs' in base:
        if all_kernels:
            return "sudo update-initramfs -u -k all 2>&1"
        return f"{base} 2>&1"

    return f"{base} 2>&1"


# ── SELinux / AppArmor 状态 ──

def get_mac_status() -> Dict:
    """获取强制访问控制 (MAC) 状态: SELinux / AppArmor。"""
    result = {
        "selinux": {"installed": False, "enabled": False, "mode": "", "policy": ""},
        "apparmor": {"installed": False, "enabled": False, "profiles_loaded": 0, "profiles_enforce": 0},
    }
    # SELinux
    _, code = run_cmd("which getenforce 2>/dev/null")
    if code == 0:
        result["selinux"]["installed"] = True
        out, _ = run_cmd("getenforce 2>/dev/null")
        result["selinux"]["mode"] = out.strip()
        result["selinux"]["enabled"] = out.strip() != "Disabled"
        policy_out, _ = run_cmd("cat /etc/selinux/config 2>/dev/null | grep ^SELINUXTYPE= | cut -d= -f2")
        result["selinux"]["policy"] = policy_out.strip()

    # AppArmor
    _, code = run_cmd("which aa-status 2>/dev/null")
    if code == 0:
        result["apparmor"]["installed"] = True
        out, _ = run_cmd("sudo aa-status 2>/dev/null")
        result["apparmor"]["enabled"] = "apparmor module is loaded" in out.lower()
        for line in out.splitlines():
            if "profiles are loaded" in line:
                try:
                    result["apparmor"]["profiles_loaded"] = int(line.split()[0])
                except ValueError:
                    pass
            if "profiles are in enforce mode" in line:
                try:
                    result["apparmor"]["profiles_enforce"] = int(line.split()[0])
                except ValueError:
                    pass

    return result


def set_selinux_mode(mode: str) -> Tuple[bool, str]:
    if mode not in ("enforcing", "permissive", "disabled"):
        return False, "模式必须是 enforcing / permissive / disabled"
    if mode == "disabled":
        out, code = run_cmd(f"sudo sed -i 's/^SELINUX=.*/SELINUX=disabled/' /etc/selinux/config 2>&1", timeout=10)
        return code == 0, out.strip() + " (需重启生效)"
    out, code = run_cmd(f"sudo setenforce {'1' if mode == 'enforcing' else '0'} 2>&1", timeout=10)
    return code == 0, out.strip()
