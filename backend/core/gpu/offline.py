"""Offline NVIDIA driver package generation / installation."""
import os
import re
import time
import json
import tarfile
from typing import Dict, List, Tuple, Optional
from utils.helpers import safe_quote, safe_temp_file
from core.distro import detect_distro, get_arch
from ._common import OFFLINE_PKG_DIR, OFFLINE_GENERATE_DIR, _PKG_RE, INITRAMFS_CMDS
from .detect import _update_initramfs_cmd


def generate_offline_package(params: Dict) -> Tuple[Optional[str], Optional[str]]:
    distro = detect_distro()
    pm = distro["pkg_manager"]
    pkgs = params.get("packages", [])
    if not pkgs: return None, "未选择任何包"
    for p in pkgs:
        if not _PKG_RE.match(p): return None, f"Invalid: {p}"
    include_deps = params.get("include_deps", True)
    pkg_name = params.get("name", f"nvidia-{distro['id']}-{distro.get('version', 'local')}")
    desc = params.get("description", f"NVIDIA offline for {distro['pretty_name']}")
    target_iso = params.get("target_iso", "")
    work = os.path.join(OFFLINE_GENERATE_DIR, pkg_name)
    pkg_dir = os.path.join(work, "packages")
    scripts = os.path.join(work, "scripts")
    pkg_list = " ".join(safe_quote(p) for p in pkgs)
    cmds: List[str] = []
    cmds.append(f"sudo mkdir -p {safe_quote(pkg_dir)} {safe_quote(scripts)}")
    cmds.append(f"sudo chmod 777 {safe_quote(work)} {safe_quote(pkg_dir)} {safe_quote(scripts)}")
    cmds.append("echo '[1/5] Downloading packages...'")
    if pm == "apt":
        # Use apt-get download --recurse for explicit dependency resolution
        dl_dir = safe_quote(os.path.join(work, "_dl_tmp"))
        cmds.append(f"mkdir -p {dl_dir}")
        cmds.append(f"cd {dl_dir}")
        if include_deps:
            # --recurse downloads the package and all its dependencies
            cmds.append(f"apt-get download --recurse {pkg_list} 2>&1 || echo 'WARNING: Some packages may not have been downloaded'")
        else:
            cmds.append(f"apt-get download {pkg_list} 2>&1 || echo 'WARNING: Some packages may not have been downloaded'")
        # Also pull any already-cached deps
        cmds.append(f"sudo apt-get install -y --download-only {pkg_list} 2>&1 || echo 'WARNING: apt-get download-only had issues'")
        # Collect all .deb files into pkg_dir
        cmds.append(f"cp {dl_dir}/*.deb {safe_quote(pkg_dir)}/ 2>/dev/null || echo 'WARNING: No .deb files in download dir'")
        cmds.append(f"cp /var/cache/apt/archives/*.deb {safe_quote(pkg_dir)}/ 2>/dev/null || echo 'WARNING: No cached .deb files'")
        # Deduplicate by filename (newer wins)
        cmds.append(f"cd {safe_quote(pkg_dir)} && for f in *.deb; do [ -f \"$f\" ] || continue; done")
        cmds.append(f"rm -rf {dl_dir}")
    elif pm == "pacman":
        # Download to cache then copy
        cmds.append(f"sudo pacman -Sw --noconfirm {pkg_list} 2>&1 || echo 'WARNING: pacman download had issues'")
        if include_deps:
            # Also resolve and download dependencies
            cmds.append(f"sudo pacman -Sw --noconfirm --asdeps {pkg_list} 2>&1 || echo 'WARNING: pacman dep download had issues'")
        cmds.append(f"cp /var/cache/pacman/pkg/*.pkg.tar.zst {safe_quote(pkg_dir)}/ 2>/dev/null || echo 'WARNING: No .pkg.tar.zst files found'")
        cmds.append(f"cp /var/cache/pacman/pkg/*.pkg.tar.xz {safe_quote(pkg_dir)}/ 2>/dev/null || echo 'WARNING: No .pkg.tar.xz files found'")
    elif pm in ("dnf", "yum"):
        # dnf/yum download --resolve handles deps automatically
        cmds.append(f"sudo {pm} download --destdir={safe_quote(pkg_dir)} --resolve {pkg_list} 2>&1 || echo 'WARNING: Package download had issues'")
        if not include_deps:
            # If deps not wanted, re-download without --resolve
            cmds.append(f"sudo {pm} download --destdir={safe_quote(pkg_dir)} {pkg_list} 2>&1 || echo 'WARNING: Package download had issues'")
    cmds.append("echo '[2/5] Verifying...'")
    ext = {"apt": "deb", "pacman": "pkg.tar.zst"}.get(pm, "rpm")
    cmds.append(f"PKG_COUNT=$(ls {safe_quote(pkg_dir)}/*.{ext} 2>/dev/null | wc -l)")
    cmds.append("[ \"$PKG_COUNT\" -gt 0 ] || { echo 'ERROR: No packages'; exit 1; }")
    cmds.append("echo '[3/5] Writing metadata...'")
    ver = _extract_version(pkgs)
    meta = {
        "name": pkg_name,
        "version": ver,
        "description": desc,
        "target_os": f"{distro['id']}-{distro.get('version','')}",
        "target_pretty_name": distro.get("pretty_name", ""),
        "target_iso": target_iso,
        "target_arch": get_arch(),
        "driver_version": ver,
        "packages": pkgs,
        "package_manager": pm,
        "include_deps": include_deps,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    tmp_json = safe_temp_file(suffix=".json", content=json.dumps(meta, indent=2, ensure_ascii=False))
    cmds.append(f"sudo cp {safe_quote(tmp_json)} {safe_quote(work)}/drv_list.json && rm -f {safe_quote(tmp_json)}")
    cmds.append("echo '[4/5] Install script...'")
    tmp_sh = safe_temp_file(suffix=".sh", content=_make_install_script(distro, pm))
    os.chmod(tmp_sh, 0o755)
    cmds.append(f"sudo cp {safe_quote(tmp_sh)} {safe_quote(work)}/install.sh && sudo chmod +x {safe_quote(work)}/install.sh && rm -f {safe_quote(tmp_sh)}")
    cmds.append("echo '[5/5] Packing...'")
    tar_path = os.path.join(OFFLINE_GENERATE_DIR, f"{pkg_name}.tar.gz")
    cmds.append(f"cd {safe_quote(work)} && sudo tar czf {safe_quote(tar_path)} . 2>&1")
    cmds.append(f"sudo chmod 666 {safe_quote(tar_path)}")
    cmds.append(f"echo '✓ Created: {tar_path}'")
    return " && ".join(cmds), None


def _extract_version(pkgs: List[str]) -> str:
    for p in pkgs:
        m = re.search(r'(\d{3,4}\.\d{2,3})', p)
        if m: return m.group(1)
    return "latest"


def _get_distro_install_block(pm: str, distro_id: str = "") -> str:
    """Return distribution-specific package install shell block."""
    distro_id = (distro_id or "").lower()

    if pm == "apt":
        # Debian / Ubuntu / Kylin / Deepin / UOS — all dpkg-based
        return '''
# --- Debian/Ubuntu/Kylin/UOS dpkg install ---
cd "$PKG_DIR"
# 1) Install kernel headers / DKMS first (module build depends on these)
for f in *dkms* *headers* *kmod*; do
    [ -f "$f" ] || continue
    if ! dpkg -i --force-depends "$f" 2>&1; then
        echo "WARNING: Failed to install $f (DKMS/headers may be optional)"
    fi
done
# 2) Install libs (libnvidia-*, libcuda*, etc.)
for f in lib*.deb lib32*.deb; do
    [ -f "$f" ] || continue
    if ! dpkg -i --force-depends "$f" 2>&1; then
        echo "WARNING: Failed to install $f (lib)"
    fi
done
# 3) Install main driver + utils (CRITICAL — fail hard on error)
for f in nvidia*.deb; do
    [ -f "$f" ] || continue
    if ! dpkg -i --force-depends "$f" 2>&1; then
        echo "ERROR: Failed to install driver package $f"
        exit 1
    fi
done
# 4) Install remaining packages (cuda, container-toolkit, etc.)
for f in *.deb; do
    [ -f "$f" ] || continue
    dpkg -s "${f%%_*}" >/dev/null 2>&1 && continue  # already installed
    dpkg -i --force-depends "$f" 2>&1 || echo "WARNING: Failed to install $f"
done
# 5) Fix broken dependencies
apt-get install -f -y 2>&1 || echo "WARNING: apt-get install -f had issues"'''

    elif pm == "pacman":
        return '''
# --- Arch/Manjaro pacman install ---
cd "$PKG_DIR"
# pacman -U handles dependency resolution internally
if ! pacman -U --noconfirm --overwrite "*.pkg.tar.zst" --overwrite "*.pkg.tar.xz" \\
    *.pkg.tar.zst *.pkg.tar.xz 2>&1; then
    echo "ERROR: pacman installation failed"
    exit 1
fi'''

    elif pm == "dnf":
        return '''
# --- Fedora/RHEL dnf install ---
cd "$PKG_DIR"
if ! rpm -ivh --force --nodeps *.rpm 2>&1; then
    if ! dnf install -y *.rpm 2>&1; then
        echo "ERROR: RPM installation failed"
        exit 1
    fi
fi'''

    elif pm == "yum":
        return '''
# --- CentOS/RHEL yum install ---
cd "$PKG_DIR"
if ! rpm -ivh --force --nodeps *.rpm 2>&1; then
    if ! yum install -y *.rpm 2>&1; then
        echo "ERROR: RPM installation failed"
        exit 1
    fi
fi'''

    elif pm == "zypper":
        return '''
# --- openSUSE zypper install ---
cd "$PKG_DIR"
if ! rpm -ivh --force --nodeps *.rpm 2>&1; then
    if ! zypper install -y *.rpm 2>&1; then
        echo "ERROR: RPM installation failed"
        exit 1
    fi
fi'''

    # Fallback: try to detect format
    return '''
# --- Auto-detect install ---
cd "$PKG_DIR"
if ls *.deb >/dev/null 2>&1; then
    for f in *.deb; do
        if ! dpkg -i --force-depends "$f" 2>&1; then
            echo "ERROR: Failed to install $f"
            exit 1
        fi
    done
    apt-get install -f -y 2>&1 || echo "WARNING: apt-get install -f had issues"
elif ls *.rpm >/dev/null 2>&1; then
    if ! rpm -ivh --force --nodeps *.rpm 2>&1; then
        echo "WARNING: RPM install had errors"
    fi
elif ls *.pkg.tar.* >/dev/null 2>&1; then
    if ! pacman -U --noconfirm --overwrite "*" *.pkg.tar.* 2>&1; then
        echo "ERROR: pacman install failed"
        exit 1
    fi
else
    echo "ERROR: No supported packages found"
    exit 1
fi'''


def _get_initramfs_cmd(pm: str) -> str:
    """Return initramfs update command for the given package manager."""
    cmd = INITRAMFS_CMDS.get(pm, 'sudo update-initramfs -u')
    return cmd.replace('sudo ', '', 1)


def _make_install_script(distro_info: Dict, pm: str) -> str:
    """Generate a distro-aware install script for offline packages."""
    dm_list = "sddm gdm gdm3 lightdm lxdm lxdm-greeter ukui-greeter"
    distro_id = distro_info.get("id", "")
    pkg_install = _get_distro_install_block(pm, distro_id)
    initramfs_cmd = _get_initramfs_cmd(pm)

    return f'''#!/bin/bash
# Linux Toolbox - Offline NVIDIA Driver Installer
# Auto-generated for: {distro_info.get("pretty_name", "Unknown")} ({pm})

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="$SCRIPT_DIR/packages"

# ── Preflight ──
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root"
    exit 1
fi

if [ -f "$SCRIPT_DIR/drv_list.json" ]; then
    DRV_VER=$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$SCRIPT_DIR/drv_list.json" | head -1 | cut -d'"' -f4)
    echo "=== NVIDIA Driver Offline Installer ==="
    echo "Driver version: $DRV_VER"
    echo "Target: {distro_info.get("pretty_name", "Unknown")}"
    echo ""
fi

# ── Step 1: Blacklist nouveau ──
echo "[1/7] Blacklisting nouveau..."
cat > /etc/modprobe.d/blacklist-nouveau.conf << 'NOUVEAU'
blacklist nouveau
options nouveau modeset=0
NOUVEAU

# ── Step 2: Stop display manager (optional, best-effort) ──
echo "[2/7] Stopping display manager..."
DM=""
for dm in {dm_list}; do
    if systemctl is-active --quiet "$dm" 2>/dev/null; then
        DM="$dm"
        systemctl stop "$dm" 2>/dev/null || echo "  WARNING: Could not stop $dm"
        echo "  Stopped $dm"
        break
    fi
done

# ── Step 3: Unload nouveau (optional) ──
if lsmod | grep -q nouveau; then
    echo "[3/7] Unloading nouveau module..."
    modprobe -r nouveau 2>/dev/null || rmmod nouveau 2>/dev/null || echo "  WARNING: Could not unload nouveau"
    sleep 1
fi

# ── Step 4: Install packages (CRITICAL) ──
echo "[4/7] Installing driver packages..."
if [ ! -d "$PKG_DIR" ]; then
    echo "ERROR: packages/ directory not found at $PKG_DIR"
    [ -n "$DM" ] && systemctl start "$DM" 2>/dev/null || true
    exit 1
fi
{pkg_install}

# ── Step 5: Update initramfs ──
echo "[5/7] Updating initramfs..."
{initramfs_cmd} 2>/dev/null || echo "WARNING: initramfs update failed — manual update may be needed after reboot"

# ── Step 6: Configure modeset + load modules ──
echo "[6/7] Configuring nvidia-drm modeset and loading modules..."
echo "options nvidia-drm modeset=1" > /etc/modprobe.d/nvidia-drm.conf

# Load nvidia kernel modules (best-effort, may fail if no GPU or secure boot)
modprobe nvidia 2>/dev/null || echo "  WARNING: nvidia module not loaded (may need reboot or signing)"
modprobe nvidia-modeset 2>/dev/null || echo "  WARNING: nvidia-modeset module not loaded (may need reboot or signing)"
modprobe nvidia-drm 2>/dev/null || echo "  WARNING: nvidia-drm module not loaded (may need reboot or signing)"
modprobe nvidia-uvm 2>/dev/null || echo "  WARNING: nvidia-uvm module not loaded (may need reboot or signing)"

# ── Step 7: Verify ──
echo "[7/7] Verifying installation..."

MODULE_LOADED=false
if lsmod | grep -q nvidia; then
    echo "  ✓ nvidia kernel module loaded"
    MODULE_LOADED=true
else
    echo "  ✗ nvidia kernel module NOT loaded"
    echo "    This usually means a reboot is required."
    echo "    After reboot, run: lsmod | grep nvidia"
    echo "    If still failing: dmesg | grep nvidia"
fi

SMI_OK=false
if command -v nvidia-smi &>/dev/null; then
    if nvidia-smi >/dev/null 2>&1; then
        echo "  ✓ nvidia-smi working"
        SMI_OK=true
        echo ""
        nvidia-smi
    else
        echo "  ✗ nvidia-smi exists but failed (module may need reboot)"
    fi
else
    echo "  ✗ nvidia-smi not found in PATH"
fi

echo ""
if [ "$MODULE_LOADED" = true ] && [ "$SMI_OK" = true ]; then
    echo "=== Installation completed successfully ==="
else
    echo "=== Installation finished with warnings ==="
    echo "A reboot is recommended. After reboot:"
    echo "  1. Run: nvidia-smi"
    echo "  2. If failing: dmesg | grep -i nvidia"
    echo "  3. Check: modinfo nvidia"
fi

# ── Restart display manager (best-effort) ──
if [ -n "$DM" ]; then
    echo ""
    echo "Restarting display manager ($DM)..."
    systemctl start "$DM" 2>/dev/null || echo "  WARNING: Could not restart $DM"
fi
'''


def parse_offline_package(tar_path: str) -> Tuple[Optional[Dict], Optional[str]]:
    if not os.path.isfile(tar_path): return None, "文件不存在"
    try:
        if not tarfile.is_tarfile(tar_path): return None, "不是有效的 tar 文件"
    except Exception:
        return None, "无法读取文件"

    extract_dir = os.path.join(OFFLINE_PKG_DIR, os.path.basename(tar_path).replace(".tar.gz", "").replace(".tgz", ""))
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            # Security: check for path traversal
            for member in tf.getmembers():
                member_path = os.path.join(extract_dir, member.name)
                real_path = os.path.realpath(member_path)
                if not real_path.startswith(os.path.realpath(extract_dir)):
                    return None, f"Path traversal detected in archive: {member.name}"
            tf.extractall(extract_dir)
    except Exception as e:
        return None, f"解压失败: {e}"

    result: Dict = {"extract_dir": extract_dir, "meta": {}, "packages": [], "install_script": None}
    drv = os.path.join(extract_dir, "drv_list.json")
    if os.path.exists(drv):
        try:
            with open(drv) as f: result["meta"] = json.load(f)
        except Exception as e: result["meta"] = {"error": str(e)}
    sh = os.path.join(extract_dir, "install.sh")
    if not os.path.exists(sh):
        sh = os.path.join(extract_dir, "scripts", "install.sh")
    if os.path.exists(sh): os.chmod(sh, 0o755); result["install_script"] = sh
    pkg_dir = os.path.join(extract_dir, "packages")
    if os.path.isdir(pkg_dir):
        for f in sorted(os.listdir(pkg_dir)):
            fp = os.path.join(pkg_dir, f)
            if f.endswith((".deb", ".rpm", ".pkg.tar.zst")): result["packages"].append({"name": f, "path": fp, "size": os.path.getsize(fp)})
    return result, None


def list_offline_packages() -> List[Dict]:
    packages: List[Dict] = []
    if not os.path.isdir(OFFLINE_PKG_DIR): return packages
    for d in os.listdir(OFFLINE_PKG_DIR):
        dp = os.path.join(OFFLINE_PKG_DIR, d)
        if os.path.isdir(dp):
            meta: Dict = {}
            drv = os.path.join(dp, "drv_list.json")
            if os.path.exists(drv):
                try:
                    with open(drv) as f: meta = json.load(f)
                except Exception: pass
            pkg_dir = os.path.join(dp, "packages")
            has_script = os.path.exists(os.path.join(dp, "install.sh")) or os.path.exists(os.path.join(dp, "scripts", "install.sh"))
            packages.append({"name": d, "path": dp, "meta": meta, "package_count": len(os.listdir(pkg_dir)) if os.path.isdir(pkg_dir) else 0, "has_install_script": has_script})
    return packages


def list_generated_packages() -> List[Dict]:
    packages: List[Dict] = []
    if not os.path.isdir(OFFLINE_GENERATE_DIR): return packages
    for f in os.listdir(OFFLINE_GENERATE_DIR):
        if f.endswith(".tar.gz") or f.endswith(".tgz"):
            fp = os.path.join(OFFLINE_GENERATE_DIR, f)
            ed = os.path.join(OFFLINE_GENERATE_DIR, f.replace(".tar.gz", "").replace(".tgz", ""))
            meta: Dict = {}
            drv = os.path.join(ed, "drv_list.json")
            if os.path.exists(drv):
                try:
                    with open(drv) as jf: meta = json.load(jf)
                except Exception: pass
            packages.append({"name": f, "path": fp, "extract_dir": ed, "size": os.path.getsize(fp), "meta": meta})
    return packages


def delete_offline_package(path: str) -> Tuple[bool, str]:
    import shutil
    real = os.path.realpath(path)
    if not real.startswith(OFFLINE_PKG_DIR) and not real.startswith(OFFLINE_GENERATE_DIR): return False, "Access denied"
    if os.path.isdir(real): shutil.rmtree(real); return True, f"Deleted: {real}"
    if os.path.isfile(real): os.remove(real); return True, f"Deleted: {real}"
    return False, "Not found"


def install_offline_package(extract_dir: str, params: Optional[Dict] = None) -> Tuple[Optional[str], Optional[str]]:
    """Install from an extracted offline package with multi-pm support."""
    params = params or {}
    real = os.path.realpath(extract_dir)
    if not os.path.isdir(real): return None, "目录不存在"
    distro = detect_distro()
    pm = distro["pkg_manager"]
    cmds: List[str] = ["echo 'Offline NVIDIA Installation'"]

    # Try install script first
    sh = os.path.join(real, "scripts", "install.sh")
    if not os.path.exists(sh):
        sh = os.path.join(real, "install.sh")
    if params.get("use_install_script", True) and os.path.exists(sh):
        os.chmod(sh, 0o755)
        cmds.append(f"cd {safe_quote(real)} && sudo bash {safe_quote(sh)}")
        return " && ".join(cmds), None

    # Fallback: detect package format and install
    pkg_dir = os.path.join(real, "packages")
    if not os.path.isdir(pkg_dir): return None, "packages 目录不存在"
    all_files = sorted(os.listdir(pkg_dir))

    # Detect package format
    deb_files = [f for f in all_files if f.endswith(".deb")]
    rpm_files = [f for f in all_files if f.endswith(".rpm")]
    pkg_files = [f for f in all_files if f.endswith(".pkg.tar.zst") or f.endswith(".pkg.tar.xz")]

    if params.get("install_dkms_first"):
        dkms = [f for f in all_files if "dkms" in f.lower() or "kernel" in f.lower()]
        other = [f for f in all_files if f not in dkms]
        ordered = dkms + other
    else: ordered = all_files

    force = params.get("force_reinstall", False)

    if deb_files and pm in ("apt",):
        # Install .deb packages with proper dependency handling.
        # Normal mode: install packages, then fix any missing dependencies with apt-get.
        # Force mode: add --force-overwrite to handle file conflicts during reinstall.
        for f in ordered:
            fp = os.path.join(pkg_dir, f)
            if not os.path.isfile(fp) or not f.endswith(".deb"): continue
            cmds.append(f"echo '  {f}'")
            if force:
                cmds.append(f"sudo dpkg --force-overwrite -i {safe_quote(fp)} 2>&1 || echo 'WARNING: Failed to install {f}'")
            else:
                cmds.append(f"sudo dpkg -i {safe_quote(fp)} 2>&1 || echo 'WARNING: Failed to install {f}'")
        # Fix any remaining dependency issues
        cmds.append("sudo apt-get install -f -y 2>&1 || echo 'WARNING: apt-get fix-deps had issues'")
    elif rpm_files and pm in ("dnf", "yum", "zypper"):
        # Install .rpm packages — try normal install first, then use the native
        # package manager to resolve dependencies.  Only use --force --nodeps
        # when the user explicitly requests a force reinstall.
        if force:
            rpm_flags = "--force --nodeps"
        else:
            rpm_flags = ""
        if pm == "dnf":
            cmds.append(
                f"cd {safe_quote(pkg_dir)} && "
                f"sudo rpm -ivh {rpm_flags} *.rpm 2>&1 || "
                f"sudo dnf install -y *.rpm 2>&1"
            )
        elif pm == "yum":
            cmds.append(
                f"cd {safe_quote(pkg_dir)} && "
                f"sudo rpm -ivh {rpm_flags} *.rpm 2>&1 || "
                f"sudo yum install -y *.rpm 2>&1"
            )
        else:
            cmds.append(
                f"cd {safe_quote(pkg_dir)} && "
                f"sudo rpm -ivh {rpm_flags} *.rpm 2>&1 || "
                f"sudo zypper install -y *.rpm 2>&1"
            )
    elif pkg_files and pm == "pacman":
        cmds.append(
            f"cd {safe_quote(pkg_dir)} && "
            f"sudo pacman -U --noconfirm *.pkg.tar.zst *.pkg.tar.xz 2>&1"
        )
    else:
        return None, f"No compatible packages found for {pm}"

    # Post-install: initramfs + modeset + modprobe + verify
    cmds.append("echo 'Updating initramfs...'")
    _update_initramfs_cmd(cmds)
    cmds.append("echo 'options nvidia-drm modeset=1' | sudo tee /etc/modprobe.d/nvidia-drm.conf >/dev/null")
    cmds.append("sudo modprobe nvidia 2>/dev/null || echo 'WARNING: nvidia module not loaded'")
    cmds.append("sudo modprobe nvidia-modeset 2>/dev/null || echo 'WARNING: nvidia-modeset module not loaded'")
    cmds.append("sudo modprobe nvidia-drm 2>/dev/null || echo 'WARNING: nvidia-drm module not loaded'")
    cmds.append("nvidia-smi 2>/dev/null && echo '✓ 安装完成，nvidia-smi 正常' || echo '⚠ 安装完成但 nvidia-smi 不可用，建议重启后检查: dmesg | grep nvidia'")
    return " && ".join(cmds), None
