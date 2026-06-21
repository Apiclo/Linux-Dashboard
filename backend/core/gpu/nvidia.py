"""NVIDIA driver install / uninstall / compatibility."""
import os
import re
from typing import Dict, List, Tuple, Optional
from utils.helpers import run_cmd, safe_quote
from core.distro import detect_distro, detect_aur_helper
from ._common import _version_cache, _PKG_RE, _cached
from .detect import _update_initramfs_cmd, check_nouveau, get_display_manager, get_running_kernel, get_kernel_headers_path, check_secure_boot
from .cuda import _fetch_web_versions


def get_nvidia_repo_versions() -> List[Dict]:
    return _cached("nv_versions", _get_nvidia_repo_versions_impl)


def _get_nvidia_repo_versions_impl() -> List[Dict]:
    distro = detect_distro()
    versions: List[Dict] = []
    aur = detect_aur_helper()
    pm = distro["pkg_manager"]
    if pm == "apt":
        out, _ = run_cmd("apt-cache search '^nvidia-driver-[0-9]' 2>/dev/null | sort -V")
        for line in out.splitlines():
            parts = line.split(" - ", 1)
            if parts:
                pkg = parts[0].strip()
                ver = pkg.replace("nvidia-driver-", "")
                if ver.isdigit(): versions.append({"package": pkg, "version": ver, "description": parts[1] if len(parts) > 1 else "", "source": "repo"})
    elif pm == "pacman":
        out, _ = run_cmd("pacman -Ss nvidia 2>/dev/null")
        seen = set()
        for line in out.splitlines():
            if not line.startswith(" ") and "/" in line:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0].split("/")[-1]
                    if name in ("nvidia", "nvidia-dkms", "nvidia-open", "nvidia-open-dkms", "nvidia-utils", "nvidia-settings", "lib32-nvidia-utils", "cuda") and name not in seen:
                        seen.add(name)
                        versions.append({"package": name, "version": parts[1], "description": " ".join(parts[2:]) if len(parts) > 2 else "", "source": "official"})
        if aur:
            for pkg in ["nvidia-beta", "nvidia-dkms-beta", "nvidia-open-beta"]:
                out, _ = run_cmd(f"{aur} -Ss {pkg} 2>/dev/null | head -3")
                for line in out.splitlines():
                    if not line.startswith(" ") and "/" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0].split("/")[-1]
                            if name not in seen: seen.add(name); versions.append({"package": name, "version": parts[1], "description": "[AUR]", "source": "aur"})
    elif pm in ("dnf", "yum"):
        out, _ = run_cmd(f"{pm} search nvidia-driver 2>/dev/null")
        for line in out.splitlines():
            if "nvidia-driver" in line.lower():
                parts = line.split()
                if parts: versions.append({"package": parts[0].strip(), "version": re.sub(r'[^\d.]', '', parts[0].split("nvidia-driver")[-1]) or "latest", "description": line.strip(), "source": "repo"})
    if not versions:
        for v in _fetch_web_versions(): versions.append({"package": f"nvidia-driver-{v}", "version": v, "description": "(web)", "source": "web"})
    return versions


def install_nvidia_repo(params: Dict) -> str:
    distro = detect_distro()
    pm = distro["pkg_manager"]
    pkg = params.get("package", "")
    if pkg and not _PKG_RE.match(pkg): return f"echo 'ERROR: Invalid package name' && exit 1"
    cmds: List[str] = []
    pkgs: List[str] = []
    if params.get("open"): pkgs.append("nvidia-open" if pm == "pacman" else "nvidia-driver-open")
    else:
        pkgs.append(pkg)
        if params.get("dkms"):
            if pm == "pacman": pkgs = ["nvidia-dkms"]
            elif pm == "apt": pkgs.append(f"nvidia-dkms-{pkg.split('-')[-1]}" if "driver" in pkg else "nvidia-dkms")
    if params.get("utils", True):
        if pm == "pacman": pkgs.append("nvidia-utils")
        elif pm == "apt": pkgs.append(f"nvidia-utils-{pkg.split('-')[-1]}" if "driver" in pkg else "nvidia-utils")
    if params.get("settings"): pkgs.append("nvidia-settings")
    if params.get("lib32"):
        if pm == "pacman": pkgs.append("lib32-nvidia-utils")
        elif pm == "apt": cmds.append("sudo dpkg --add-architecture i386 && sudo apt-get update -y")
    if params.get("cuda"): pkgs.append("cuda" if pm == "pacman" else "nvidia-cuda-toolkit")
    if params.get("container_toolkit"): pkgs.append("nvidia-container-toolkit")
    if params.get("persistenced"): pkgs.append("nvidia-persistenced")
    if params.get("fabricmanager"):
        if pm == "pacman": pkgs.append("nvidia-fabricmanager")
        elif pm == "apt": pkgs.append(f"nvidia-fabricmanager-{pkg.split('-')[-1]}" if "driver" in pkg else "nvidia-fabricmanager")
        else: pkgs.append("nvidia-fabricmanager")
    if params.get("egl"):
        if pm == "pacman": pkgs.append("egl-wayland")
        elif pm == "apt": pkgs.append("libnvidia-egl-wayland1")
        else: pkgs.append("libnvidia-egl-wayland")
    if pm == "apt": cmds.append(f"sudo apt-get update -y && sudo apt-get install -y {' '.join(safe_quote(p) for p in pkgs)}")
    elif pm == "pacman":
        aur = detect_aur_helper()
        if aur and any("beta" in p for p in pkgs): cmds.append(f"{aur} -S --noconfirm {' '.join(safe_quote(p) for p in pkgs)}")
        else: cmds.append(f"sudo pacman -S --noconfirm {' '.join(safe_quote(p) for p in pkgs)}")
    elif pm in ("dnf", "yum"): cmds.append(f"sudo {pm} install -y {' '.join(safe_quote(p) for p in pkgs)}")
    if params.get("modeset"):
        cmds.append("echo 'options nvidia-drm modeset=1' | sudo tee /etc/modprobe.d/nvidia-drm.conf")
    # Post-install: load modules and verify
    cmds.append("sudo modprobe nvidia 2>/dev/null || true")
    cmds.append("sudo modprobe nvidia-modeset 2>/dev/null || true")
    cmds.append("sudo modprobe nvidia-drm 2>/dev/null || true")
    _update_initramfs_cmd(cmds)
    cmds.append("if lsmod | grep -q nvidia; then echo '✓ nvidia module loaded'; else echo '⚠ nvidia module not loaded — reboot may be required'; fi")
    cmds.append("nvidia-smi 2>/dev/null && echo '✓ nvidia-smi OK' || echo '⚠ nvidia-smi not available'")
    return " && ".join(cmds)


def validate_runfile(path: str) -> Tuple[bool, str]:
    if not path: return False, "路径为空"
    real = os.path.realpath(path)
    if not os.path.exists(real): return False, f"文件不存在: {real}"
    if not real.endswith(".run"): return False, "不是 .run 文件"
    if os.path.getsize(real) < 1024 * 1024: return False, "文件过小"
    return True, f"文件有效 ({os.path.getsize(real) / 1024 / 1024:.1f} MB)"


def get_runfile_info(path: str) -> Tuple[Optional[Dict], Optional[str]]:
    ok, msg = validate_runfile(path)
    if not ok: return None, msg
    real = os.path.realpath(path)
    out, code = run_cmd(f"sh {safe_quote(real)} --info 2>/dev/null | head -20", timeout=10)
    if code == 0 and out: return {"info": out, "path": real}, None
    fname = os.path.basename(real)
    ver = re.search(r'(\d{3}\.\d{2,3})', fname)
    return {"info": f"Filename: {fname}", "version": ver.group(1) if ver else "unknown", "path": real}, None


def install_nvidia_runfile(params: Dict) -> Tuple[Optional[str], Optional[str]]:
    path = params.get("path", "")
    ok, msg = validate_runfile(path)
    if not ok: return None, msg
    real = os.path.realpath(path)
    nouveau = check_nouveau()
    if nouveau["loaded"] and not params.get("no_nouveau_check") and not params.get("force"):
        return None, "NOUVEAU_LOADED: nouveau 仍在加载！"
    dm = get_display_manager()
    kernel = get_running_kernel()
    headers = get_kernel_headers_path()
    cmds: List[str] = ["set -e"]
    cmds.append("echo '========================================'")
    cmds.append("echo '  NVIDIA .run Installation'")
    cmds.append("echo '========================================'")
    if params.get("blacklist_nouveau") and not nouveau["blacklisted"]:
        cmds.append("echo 'Blacklisting nouveau...'")
        cmds.append("echo 'blacklist nouveau' | sudo tee /etc/modprobe.d/blacklist-nouveau.conf")
        cmds.append("echo 'options nouveau modeset=0' | sudo tee -a /etc/modprobe.d/blacklist-nouveau.conf")
        _update_initramfs_cmd(cmds)
    if dm and params.get("stop_dm", True):
        cmds.append(f"echo 'Stopping {dm}...'")
        cmds.append(f"sudo systemctl stop {safe_quote(dm)} 2>/dev/null || true")
        cmds.append("sleep 2")
    cmds.append("echo 'Running installer...'")
    args = [f"sudo sh {safe_quote(real)}"]
    if params.get("dkms"): args.append("--dkms")
    if params.get("no_opengl", True): args.append("--no-opengl-files")
    args.append("--no-x-check")
    args.append("--no-nouveau-check")
    if params.get("silent", True): args.append("--silent")
    if headers: args.append(f"--kernel-source-path={safe_quote(headers)}")
    cmds.append(" \\\n  ".join(args))
    cmds.append("INSTALL_EXIT=$?")
    if params.get("enable_modeset", True): cmds.append("echo 'options nvidia-drm modeset=1' | sudo tee /etc/modprobe.d/nvidia-drm.conf")
    cmds.append("echo 'Updating initramfs...'")
    _update_initramfs_cmd(cmds)
    # Load nvidia modules
    cmds.append("echo 'Loading nvidia kernel modules...'")
    cmds.append("sudo modprobe nvidia 2>/dev/null || true")
    cmds.append("sudo modprobe nvidia-modeset 2>/dev/null || true")
    cmds.append("sudo modprobe nvidia-drm 2>/dev/null || true")
    cmds.append("sudo modprobe nvidia-uvm 2>/dev/null || true")
    if dm and params.get("stop_dm", True): cmds.append(f"sudo systemctl start {safe_quote(dm)} 2>/dev/null || true")
    # Verify
    cmds.append("if lsmod | grep -q nvidia; then echo '✓ nvidia module loaded'; else echo '⚠ nvidia module not loaded — reboot may be required'; fi")
    cmds.append("nvidia-smi 2>/dev/null && echo '✓ nvidia-smi OK' || echo '⚠ nvidia-smi not available — reboot may be required'")
    cmds.append("exit $INSTALL_EXIT")
    return "\n".join(cmds), None


def uninstall_nvidia() -> str:
    distro = detect_distro()
    pm = distro["pkg_manager"]
    dm = get_display_manager()
    cmds = ["set -e", "echo 'Uninstalling NVIDIA driver...'", "sudo systemctl stop nvidia-persistenced 2>/dev/null || true"]
    if dm: cmds.append(f"sudo systemctl stop {dm} 2>/dev/null || true")
    if pm == "apt": cmds.append("sudo apt-get remove --purge -y 'nvidia-*' 'libnvidia-*' 2>/dev/null || true && sudo apt-get autoremove -y")
    elif pm == "pacman": cmds.append("sudo pacman -Rns --noconfirm $(pacman -Qq | grep nvidia) 2>/dev/null || true")
    elif pm in ("dnf", "yum"): cmds.append(f"sudo {pm} remove -y '*nvidia*' 2>/dev/null || true")
    cmds.extend(["sudo rm -f /etc/modprobe.d/nvidia-*.conf /etc/modprobe.d/blacklist-nouveau.conf 2>/dev/null || true"])
    _update_initramfs_cmd(cmds)
    if dm: cmds.append(f"sudo systemctl start {dm} 2>/dev/null || true")
    cmds.append("echo '✓ Uninstalled. Please reboot.'")
    return "\n".join(cmds)


def check_compatibility() -> Dict:
    r: Dict = {"checks": [], "warnings": [], "errors": []}
    h = get_kernel_headers_path()
    if h: r["checks"].append({"name": "内核头文件", "status": "ok", "detail": h})
    else: r["errors"].append({"name": "内核头文件", "status": "missing", "detail": "未找到"})
    gcc, gc = run_cmd("gcc --version 2>/dev/null | head -1")
    if gc == 0: r["checks"].append({"name": "GCC", "status": "ok", "detail": gcc})
    else: r["warnings"].append({"name": "GCC", "status": "missing", "detail": "未找到"})
    sb = check_secure_boot()
    if sb["enabled"]: r["warnings"].append({"name": "SecureBoot", "status": "enabled", "detail": "需签名模块"})
    else: r["checks"].append({"name": "SecureBoot", "status": "disabled", "detail": "未启用"})
    n = check_nouveau()
    if n["loaded"]: r["errors"].append({"name": "nouveau", "status": "loaded", "detail": "必须禁用"})
    elif not n["blacklisted"]: r["warnings"].append({"name": "nouveau", "status": "not_blacklisted", "detail": "建议禁用"})
    return r


def list_available_nvidia_packages() -> List[Dict]:
    pm = detect_distro()["pkg_manager"]
    packages: List[Dict] = []
    if pm == "apt":
        out, _ = run_cmd("apt-cache search nvidia 2>/dev/null | sort")
        for line in out.splitlines():
            parts = line.split(" - ", 1)
            if parts and any(k in parts[0] for k in ["nvidia-driver", "nvidia-utils", "nvidia-dkms", "nvidia-settings", "nvidia-kernel", "nvidia-compute", "nvidia-cuda", "nvidia-open", "nvidia-container"]):
                packages.append({"package": parts[0].strip(), "description": parts[1].strip() if len(parts) > 1 else ""})
    elif pm == "pacman":
        out, _ = run_cmd("pacman -Ss nvidia 2>/dev/null")
        for line in out.splitlines():
            if not line.startswith(" ") and "/" in line:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0].split("/")[-1]
                    if any(k in name for k in ["nvidia", "cuda"]):
                        packages.append({"package": name, "version": parts[1], "description": " ".join(parts[2:]) if len(parts) > 2 else ""})
    return packages
