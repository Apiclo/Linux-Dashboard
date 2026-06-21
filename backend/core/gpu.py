"""GPU detection and installation."""
import os
import re
import shlex
import time
import tempfile
import json
import tarfile
import urllib.request
from typing import Dict, List, Tuple, Optional
from utils.helpers import run_cmd, safe_quote, safe_temp_file
from core.distro import detect_distro, detect_aur_helper, get_arch

OFFLINE_PKG_DIR = "/opt/linux-toolbox/nvidia-offline"
OFFLINE_GENERATE_DIR = "/opt/linux-toolbox/nvidia-generated"
_version_cache: Dict[str, Tuple[float, any]] = {}
_PKG_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._+\-:~]*$')
_CUDA_FALLBACK_VERSIONS = ["12.8", "12.6", "12.4", "12.2", "11.8"]

# ── CUDA 源配置（按发行版家族） ──
CUDA_REPO_CONFIG = {
    "ubuntu": {
        "repo_base": "https://developer.download.nvidia.com/compute/cuda/repos",
        "repo_path": "ubuntu{version}/{arch}",
        "keyring_pkg": "cuda-keyring_1.1-1_all.deb",
        "setup_cmds": [
            "wget -q {repo_base}/ubuntu{version}/{arch}/cuda-keyring_1.1-1_all.deb -O /tmp/cuda-keyring.deb",
            "sudo dpkg -i /tmp/cuda-keyring.deb",
            "sudo apt-get update -y",
        ],
        "install_cmd": "sudo apt-get install -y {packages}",
        "pkg_map": lambda v: f"cuda-toolkit-{v.replace('.', '-')}" if v else "cuda-toolkit",
    },
    "debian": {
        "repo_base": "https://developer.download.nvidia.com/compute/cuda/repos",
        "repo_path": "debian{version}/{arch}",
        "keyring_pkg": "cuda-keyring_1.1-1_all.deb",
        "setup_cmds": [
            "wget -q {repo_base}/debian{version}/{arch}/cuda-keyring_1.1-1_all.deb -O /tmp/cuda-keyring.deb",
            "sudo dpkg -i /tmp/cuda-keyring.deb",
            "sudo apt-get update -y",
        ],
        "install_cmd": "sudo apt-get install -y {packages}",
        "pkg_map": lambda v: f"cuda-toolkit-{v.replace('.', '-')}" if v else "cuda-toolkit",
    },
    "fedora": {
        "repo_base": "https://developer.download.nvidia.com/compute/cuda/repos",
        "repo_path": "fedora{version}/{arch}",
        "repo_file": "cuda-fedora.repo",
        "setup_cmds": [
            "sudo dnf config-manager --add-repo {repo_base}/fedora{version}/{arch}/cuda-fedora.repo",
        ],
        "install_cmd": "sudo dnf install -y {packages}",
        "pkg_map": lambda v: f"cuda-toolkit-{v.replace('.', '-')}" if v else "cuda-toolkit",
    },
    "rhel": {
        "repo_base": "https://developer.download.nvidia.com/compute/cuda/repos",
        "repo_path": "rhel{version}/{arch}",
        "repo_file": "cuda-rhel.repo",
        "setup_cmds": [
            "sudo dnf config-manager --add-repo {repo_base}/rhel{version}/{arch}/cuda-rhel.repo",
        ],
        "install_cmd": "sudo dnf install -y {packages}",
        "pkg_map": lambda v: f"cuda-toolkit-{v.replace('.', '-')}" if v else "cuda-toolkit",
    },
    "opensuse": {
        "repo_base": "https://developer.download.nvidia.com/compute/cuda/repos",
        "repo_path": "opensuse{version}/{arch}",
        "setup_cmds": [
            "sudo zypper addrepo -f {repo_base}/opensuse{version}/{arch} cuda",
            "sudo zypper refresh",
        ],
        "install_cmd": "sudo zypper install -y {packages}",
        "pkg_map": lambda v: f"cuda-toolkit-{v.replace('.', '-')}" if v else "cuda-toolkit",
    },
    "arch": {
        # Arch 通过 community 仓库，无需额外添加源
        "repo_base": "https://developer.download.nvidia.com/compute/cuda/repos",
        "repo_path": "",
        "setup_cmds": [],
        "install_cmd": "sudo pacman -S --noconfirm {packages}",
        "pkg_map": lambda v: "cuda cuda-tools" if v else "cuda",
    },
}


def _resolve_distro_family(distro: dict) -> str:
    """将发行版信息映射到 CUDA_REPO_CONFIG 的 key。"""
    d_id = distro.get("id", "").lower()
    d_like = distro.get("like", "").lower()
    pm = distro.get("pkg_manager", "")

    # apt 系
    if pm == "apt":
        if "ubuntu" in d_id or "ubuntu" in d_like or "kylin" in d_id or "uos" in d_id or "deepin" in d_id:
            return "ubuntu"
        return "debian"

    # dnf/yum 系 — 区分 Fedora 和 RHEL
    if pm in ("dnf", "yum"):
        rhel_ids = {"rhel", "centos", "rocky", "alma", "almalinux", "eurolinux", "anolis", "openEuler"}
        if d_id in rhel_ids or any(r in d_like for r in ("rhel", "centos")):
            return "rhel"
        return "fedora"

    # zypper
    if pm == "zypper":
        return "opensuse"

    # pacman
    if pm == "pacman":
        return "arch"

    return "ubuntu"  # fallback


def _cached(key: str, fetcher, ttl=300):
    now = time.time()
    if key in _version_cache:
        ts, val = _version_cache[key]
        if now - ts < ttl: return val
    val = fetcher()
    _version_cache[key] = (now, val)
    return val


def detect_gpus() -> List[Dict]:
    gpus: List[Dict] = []
    out, code = run_cmd("lspci -nn 2>/dev/null")
    if code != 0: return gpus
    for line in out.splitlines():
        low = line.lower()
        if "vga" in low or "3d" in low or "display" in low:
            gpu: Dict = {"raw": line}
            m = re.match(r'^([0-9a-fA-F:.]+)', line)
            if m: gpu["pci_id"] = m.group(1)
            id_m = re.search(r'\[([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\]', line)
            gpu["device_id"] = id_m.group(1) if id_m else ""
            if "nvidia" in low: gpu["vendor"] = "NVIDIA"; gpu["type"] = "nvidia"
            elif "amd" in low or "ati" in low: gpu["vendor"] = "AMD"; gpu["type"] = "amd"
            elif "intel" in low: gpu["vendor"] = "Intel"; gpu["type"] = "intel"
            else: gpu["vendor"] = "Unknown"; gpu["type"] = "unknown"
            gpu["name"] = re.sub(r'\s*\[[0-9a-fA-F:]+\]\s*$', '', line.split(":", 2)[-1].strip())
            gpus.append(gpu)
    return gpus


def get_nvidia_smi_info() -> List[Dict]:
    out, code = run_cmd("nvidia-smi --query-gpu=index,driver_version,name,temperature.gpu,memory.total,memory.used,utilization.gpu,pci.bus_id --format=csv,noheader,nounits 2>/dev/null")
    if code != 0 or not out: return []
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 7:
            gpus.append({"index": parts[0], "driver_version": parts[1], "gpu_name": parts[2], "temperature": parts[3], "vram_total": parts[4], "vram_used": parts[5], "utilization": parts[6], "pci_bus": parts[7] if len(parts) > 7 else ""})
    return gpus


def get_nvidia_driver_detail() -> Dict:
    info: Dict = {}
    ver, _ = run_cmd("cat /proc/driver/nvidia/version 2>/dev/null | head -2")
    if ver: info["proc_version"] = ver
    mod, _ = run_cmd("modinfo nvidia 2>/dev/null | grep -E '^(version|vermagic):'")
    for line in mod.splitlines():
        if "version:" in line and "vermagic" not in line: info["module_version"] = line.split(":", 1)[1].strip()
        elif "vermagic:" in line: info["vermagic"] = line.split(":", 1)[1].strip()
    return info


def check_nouveau() -> Dict:
    out, _ = run_cmd("lsmod | grep nouveau")
    loaded = bool(out.strip())
    bl, _ = run_cmd("cat /etc/modprobe.d/*nouveau* 2>/dev/null | grep -i blacklist")
    return {"loaded": loaded, "blacklisted": "blacklist" in bl.lower() if bl else False}


def blacklist_nouveau() -> Tuple[bool, str]:
    fd, tmp = tempfile.mkstemp(suffix=".conf", prefix="blacklist-nouveau-")
    try:
        os.write(fd, b"blacklist nouveau\noptions nouveau modeset=0\n")
        os.close(fd)
        _, code = run_cmd(f"sudo cp {safe_quote(tmp)} /etc/modprobe.d/blacklist-nouveau.conf")
        if code == 0: _update_initramfs(); return True, "nouveau 已加入黑名单，需要重启"
        return False, "写入失败"
    finally:
        try: os.remove(tmp)
        except OSError: pass


def check_secure_boot() -> Dict:
    mok, code = run_cmd("mokutil --sb-state 2>/dev/null")
    if code == 0 and "SecureBoot enabled" in mok: return {"enabled": True, "output": mok.strip()}
    out, _ = run_cmd("od -An -t x1 /sys/firmware/efi/efivars/SecureBoot-* 2>/dev/null | tail -1")
    if out:
        parts = out.strip().split()
        if len(parts) >= 5 and parts[4] == "01": return {"enabled": True, "output": "SecureBoot enabled"}
    return {"enabled": False, "output": mok.strip() if mok else "Not detected"}


def get_running_kernel() -> str:
    out, _ = run_cmd("uname -r")
    return out


def get_kernel_headers_path() -> str:
    kernel = get_running_kernel()
    for p in [f"/usr/src/linux-headers-{kernel}", f"/usr/src/kernels/{kernel}", f"/lib/modules/{kernel}/build"]:
        if os.path.exists(p): return p
    return ""


def get_display_manager() -> Optional[str]:
    for dm in ["sddm", "gdm", "gdm3", "lightdm", "lxdm"]:
        _, code = run_cmd(f"systemctl is-active {dm} 2>/dev/null")
        if code == 0: return dm
    return None


def get_loaded_modules() -> str:
    out, _ = run_cmd("lsmod | grep -E 'nvidia|nouveau|amdgpu|i915'")
    return out


def _update_initramfs():
    distro = detect_distro()
    pm = distro["pkg_manager"]
    if pm == "apt": run_cmd("sudo update-initramfs -u 2>/dev/null")
    elif pm == "pacman": run_cmd("sudo mkinitcpio -P 2>/dev/null")
    elif pm in ("dnf", "yum", "zypper"): run_cmd("sudo dracut --force 2>/dev/null")


def _update_initramfs_cmd(cmds: List[str]):
    distro = detect_distro()
    pm = distro["pkg_manager"]
    if pm == "apt": cmds.append("sudo update-initramfs -u 2>/dev/null || true")
    elif pm == "pacman": cmds.append("sudo mkinitcpio -P 2>/dev/null || true")
    elif pm in ("dnf", "yum", "zypper"): cmds.append("sudo dracut --force 2>/dev/null || true")


def _get_nvidia_repo_url() -> str:
    """构建 NVIDIA CUDA 仓库基础 URL（用于爬取版本信息）。"""
    distro = detect_distro()
    arch = get_arch()
    family = _resolve_distro_family(distro)
    cfg = CUDA_REPO_CONFIG.get(family, CUDA_REPO_CONFIG["ubuntu"])

    if family in ("ubuntu", "debian"):
        version = distro.get("version", "22.04")
        ver = version.replace(".", "") if family == "ubuntu" else version.split(".")[0]
        return f"{cfg['repo_base']}/{cfg['repo_path'].format(version=ver, arch=arch)}"
    elif family in ("fedora", "rhel"):
        version = distro.get("version", "39")
        ver = version.split(".")[0]
        return f"{cfg['repo_base']}/{cfg['repo_path'].format(version=ver, arch=arch)}"
    elif family == "opensuse":
        version = distro.get("version", "15")
        ver = version.split(".")[0] if "." in version else version
        return f"{cfg['repo_base']}/{cfg['repo_path'].format(version=ver, arch=arch)}"
    elif family == "arch":
        # Arch CUDA 包在 community 仓库中，版本爬取使用 Ubuntu 源作为参考
        ubuntu_cfg = CUDA_REPO_CONFIG["ubuntu"]
        return f"{ubuntu_cfg['repo_base']}/ubuntu2204/{arch}"

    # 最终 fallback
    ubuntu_cfg = CUDA_REPO_CONFIG["ubuntu"]
    return f"{ubuntu_cfg['repo_base']}/ubuntu2204/{arch}"


def _fetch_web_versions() -> List[str]:
    url = _get_nvidia_repo_url() + "/Packages"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Linux-Toolbox/3.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                seen = set()
                for line in content.splitlines():
                    if line.startswith("Package: nvidia-driver-"):
                        ver = line.split("nvidia-driver-")[-1].strip()
                        if ver.isdigit() and ver not in seen: seen.add(ver)
                return sorted(seen, key=lambda x: int(x), reverse=True)
        except Exception: time.sleep(2 ** attempt)
    return []


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


def fetch_cuda_versions() -> List[str]:
    def _f():
        url = _get_nvidia_repo_url() + "/"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Linux-Toolbox/3.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    content = resp.read().decode("utf-8", errors="ignore")
                    seen = set()
                    for line in content.splitlines():
                        m = re.search(r'cuda-toolkit-(\d+-\d+)', line)
                        if m:
                            ver = m.group(1).replace("-", ".")
                            if ver not in seen: seen.add(ver)
                    return sorted(seen, reverse=True) if seen else _CUDA_FALLBACK_VERSIONS
            except Exception: time.sleep(2 ** attempt)
        return _CUDA_FALLBACK_VERSIONS
    return _cached("cuda_ver", _f)


def get_cuda_info() -> str:
    nvcc, code = run_cmd("nvcc --version 2>/dev/null")
    if code == 0 and nvcc: return nvcc
    smi, _ = run_cmd("nvidia-smi 2>/dev/null | grep -i 'CUDA Version'")
    return smi.strip() if smi else "CUDA 未安装"


def _build_cuda_fmt(version: str = "") -> dict:
    """构建 CUDA 仓库命令的格式化变量。"""
    distro = detect_distro()
    arch = get_arch()
    family = _resolve_distro_family(distro)
    cfg = CUDA_REPO_CONFIG.get(family, CUDA_REPO_CONFIG["ubuntu"])

    raw_version = distro.get("version", "22.04")
    if family in ("ubuntu", "kylin"):
        fmt_version = raw_version.replace(".", "")
    elif family == "debian":
        fmt_version = raw_version.split(".")[0]
    elif family in ("fedora", "rhel", "opensuse"):
        fmt_version = raw_version.split(".")[0] if "." in raw_version else raw_version
    else:
        fmt_version = raw_version

    packages = cfg["pkg_map"](version) if callable(cfg["pkg_map"]) else cfg["pkg_map"]

    return {
        "repo_base": cfg["repo_base"],
        "version": fmt_version,
        "arch": arch,
        "packages": packages,
        "family": family,
        "cfg": cfg,
    }


def setup_cuda_repo() -> str:
    """仅设置 CUDA 仓库源（keyring / repo 文件），不安装任何包。"""
    fmt = _build_cuda_fmt()
    cfg = fmt.pop("cfg")
    fmt.pop("family", None)
    setup_cmds = cfg.get("setup_cmds", [])
    if not setup_cmds:
        return "echo '该发行版无需额外设置 CUDA 源（CUDA 已在官方仓库中）'"
    return " && ".join(sc.format(**fmt) for sc in setup_cmds)


def install_cuda_packages(version: str = "") -> str:
    """安装 CUDA 包（前提是 setup_cuda_repo 已执行）。"""
    fmt = _build_cuda_fmt(version)
    cfg = fmt.pop("cfg")
    fmt.pop("family", None)
    return cfg["install_cmd"].format(**fmt)


def install_cuda_toolkit(method: str = "network", version: str = "") -> str:
    """生成 CUDA 完整安装命令（设置源 + 安装）。保留兼容旧调用。"""
    if method != "network":
        return "echo '请从 https://developer.nvidia.com/cuda-downloads 下载 .run 文件，然后在自定义标签页执行'"
    setup = setup_cuda_repo()
    install = install_cuda_packages(version)
    # 如果 setup 只是 echo（无需设置源），直接返回 install
    if setup.startswith("echo "):
        return install
    return f"{setup} && {install}"


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


# ── Offline Package ──

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
    cmds: List[str] = ["set -e"]
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
            cmds.append(f"apt-get download --recurse {pkg_list} 2>&1 || true")
        else:
            cmds.append(f"apt-get download {pkg_list} 2>&1 || true")
        # Also pull any already-cached deps
        cmds.append(f"sudo apt-get install -y --download-only {pkg_list} 2>&1 || true")
        # Collect all .deb files into pkg_dir
        cmds.append(f"cp {dl_dir}/*.deb {safe_quote(pkg_dir)}/ 2>/dev/null || true")
        cmds.append(f"cp /var/cache/apt/archives/*.deb {safe_quote(pkg_dir)}/ 2>/dev/null || true")
        # Deduplicate by filename (newer wins)
        cmds.append(f"cd {safe_quote(pkg_dir)} && for f in *.deb; do [ -f \"$f\" ] || continue; done")
        cmds.append(f"rm -rf {dl_dir}")
    elif pm == "pacman":
        # Download to cache then copy
        cmds.append(f"sudo pacman -Sw --noconfirm {pkg_list} 2>&1 || true")
        if include_deps:
            # Also resolve and download dependencies
            cmds.append(f"sudo pacman -Sw --noconfirm --asdeps {pkg_list} 2>&1 || true")
        cmds.append(f"cp /var/cache/pacman/pkg/*.pkg.tar.zst {safe_quote(pkg_dir)}/ 2>/dev/null || true")
        cmds.append(f"cp /var/cache/pacman/pkg/*.pkg.tar.xz {safe_quote(pkg_dir)}/ 2>/dev/null || true")
    elif pm in ("dnf", "yum"):
        # dnf/yum download --resolve handles deps automatically
        cmds.append(f"sudo {pm} download --destdir={safe_quote(pkg_dir)} --resolve {pkg_list} 2>&1 || true")
        if not include_deps:
            # If deps not wanted, re-download without --resolve
            cmds.append(f"sudo {pm} download --destdir={safe_quote(pkg_dir)} {pkg_list} 2>&1 || true")
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
    [ -f "$f" ] && dpkg -i --force-depends "$f" 2>&1
done
# 2) Install libs (libnvidia-*, libcuda*, etc.)
for f in lib*.deb lib32*.deb; do
    [ -f "$f" ] && dpkg -i --force-depends "$f" 2>&1
done
# 3) Install main driver + utils
for f in nvidia*.deb; do
    [ -f "$f" ] && dpkg -i --force-depends "$f" 2>&1
done
# 4) Install remaining packages (cuda, container-toolkit, etc.)
for f in *.deb; do
    [ -f "$f" ] || continue
    dpkg -s "${f%%_*}" >/dev/null 2>&1 && continue  # already installed
    dpkg -i --force-depends "$f" 2>&1
done
# 5) Fix broken dependencies
apt-get install -f -y 2>&1 || true'''

    elif pm == "pacman":
        return '''
# --- Arch/Manjaro pacman install ---
cd "$PKG_DIR"
# pacman -U handles dependency resolution internally
pacman -U --noconfirm --overwrite "*.pkg.tar.zst" --overwrite "*.pkg.tar.xz" \\
    *.pkg.tar.zst *.pkg.tar.xz 2>&1'''

    elif pm == "dnf":
        return '''
# --- Fedora/RHEL dnf install ---
cd "$PKG_DIR"
rpm -ivh --force --nodeps *.rpm 2>&1 || dnf install -y *.rpm 2>&1'''

    elif pm == "yum":
        return '''
# --- CentOS/RHEL yum install ---
cd "$PKG_DIR"
rpm -ivh --force --nodeps *.rpm 2>&1 || yum install -y *.rpm 2>&1'''

    elif pm == "zypper":
        return '''
# --- openSUSE zypper install ---
cd "$PKG_DIR"
rpm -ivh --force --nodeps *.rpm 2>&1 || zypper install -y *.rpm 2>&1'''

    # Fallback: try to detect format
    return '''
# --- Auto-detect install ---
cd "$PKG_DIR"
if ls *.deb >/dev/null 2>&1; then
    for f in *.deb; do dpkg -i --force-depends "$f" 2>&1; done
    apt-get install -f -y 2>&1 || true
elif ls *.rpm >/dev/null 2>&1; then
    rpm -ivh --force --nodeps *.rpm 2>&1 || true
elif ls *.pkg.tar.* >/dev/null 2>&1; then
    pacman -U --noconfirm --overwrite "*" *.pkg.tar.* 2>&1 || true
else
    echo "ERROR: No supported packages found"
    exit 1
fi'''


def _get_initramfs_cmd(pm: str) -> str:
    """Return initramfs update command for the given package manager."""
    return {
        "apt": "update-initramfs -u",
        "dnf": "dracut --force",
        "yum": "dracut --force",
        "zypper": "dracut --force",
        "pacman": "mkinitcpio -P",
    }.get(pm, "update-initramfs -u")


def _make_install_script(distro_info: Dict, pm: str) -> str:
    """Generate a distro-aware install script for offline packages."""
    dm_list = "sddm gdm gdm3 lightdm lxdm lxdm-greeter ukui-greeter"
    distro_id = distro_info.get("id", "")
    pkg_install = _get_distro_install_block(pm, distro_id)
    initramfs_cmd = _get_initramfs_cmd(pm)

    return f'''#!/bin/bash
# Linux Toolbox - Offline NVIDIA Driver Installer
# Auto-generated for: {distro_info.get("pretty_name", "Unknown")} ({pm})
set -e

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

# ── Step 2: Stop display manager ──
echo "[2/7] Stopping display manager..."
DM=""
for dm in {dm_list}; do
    if systemctl is-active --quiet "$dm" 2>/dev/null; then
        DM="$dm"
        systemctl stop "$dm"
        echo "  Stopped $dm"
        break
    fi
done

# ── Step 3: Unload nouveau ──
if lsmod | grep -q nouveau; then
    echo "[3/7] Unloading nouveau module..."
    modprobe -r nouveau 2>/dev/null || rmmod nouveau 2>/dev/null || true
    sleep 1
fi

# ── Step 4: Install packages ──
echo "[4/7] Installing driver packages..."
if [ ! -d "$PKG_DIR" ]; then
    echo "ERROR: packages/ directory not found at $PKG_DIR"
    [ -n "$DM" ] && systemctl start "$DM"
    exit 1
fi
{pkg_install}

# ── Step 5: Update initramfs ──
echo "[5/7] Updating initramfs..."
{initramfs_cmd} 2>/dev/null || true

# ── Step 6: Configure modeset + load modules ──
echo "[6/7] Configuring nvidia-drm modeset and loading modules..."
echo "options nvidia-drm modeset=1" > /etc/modprobe.d/nvidia-drm.conf

# Load nvidia kernel modules
modprobe nvidia 2>/dev/null || true
modprobe nvidia-modeset 2>/dev/null || true
modprobe nvidia-drm 2>/dev/null || true
modprobe nvidia-uvm 2>/dev/null || true

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

# ── Restart display manager ──
if [ -n "$DM" ]; then
    echo ""
    echo "Restarting display manager ($DM)..."
    systemctl start "$DM" 2>/dev/null || true
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
    cmds: List[str] = ["set -e", "echo 'Offline NVIDIA Installation'"]

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
        # dpkg flow
        for f in ordered:
            fp = os.path.join(pkg_dir, f)
            if not os.path.isfile(fp) or not f.endswith(".deb"): continue
            cmds.append(f"echo '  {f}'")
            if force: cmds.append(f"sudo dpkg --force-overwrite -i {safe_quote(fp)} 2>&1 || true")
            else: cmds.append(f"sudo dpkg --force-depends -i {safe_quote(fp)} 2>&1 || true")
        cmds.append("sudo apt-get install -f -y 2>&1 || true")
    elif rpm_files and pm in ("dnf", "yum", "zypper"):
        # rpm flow
        if pm == "dnf":
            cmds.append(f"cd {safe_quote(pkg_dir)} && sudo rpm -ivh --force --nodeps *.rpm 2>&1 || sudo dnf install -y *.rpm 2>&1")
        elif pm == "yum":
            cmds.append(f"cd {safe_quote(pkg_dir)} && sudo rpm -ivh --force --nodeps *.rpm 2>&1 || sudo yum install -y *.rpm 2>&1")
        else:
            cmds.append(f"cd {safe_quote(pkg_dir)} && sudo rpm -ivh --force --nodeps *.rpm 2>&1 || sudo zypper install -y *.rpm 2>&1")
    elif pkg_files and pm == "pacman":
        # pacman flow
        cmds.append(f"cd {safe_quote(pkg_dir)} && sudo pacman -U --noconfirm --overwrite '*' *.pkg.tar.zst *.pkg.tar.xz 2>&1")
    else:
        return None, f"No compatible packages found for {pm}"

    # Post-install: initramfs + modeset + modprobe + verify
    cmds.append("echo 'Updating initramfs...'")
    _update_initramfs_cmd(cmds)
    cmds.append("echo 'options nvidia-drm modeset=1' | sudo tee /etc/modprobe.d/nvidia-drm.conf >/dev/null")
    cmds.append("sudo modprobe nvidia 2>/dev/null || true")
    cmds.append("sudo modprobe nvidia-modeset 2>/dev/null || true")
    cmds.append("sudo modprobe nvidia-drm 2>/dev/null || true")
    cmds.append("nvidia-smi 2>/dev/null && echo '✓ 安装完成，nvidia-smi 正常' || echo '⚠ 安装完成但 nvidia-smi 不可用，建议重启后检查: dmesg | grep nvidia'")
    return " && ".join(cmds), None


def install_amd_driver() -> str:
    pm = detect_distro()["pkg_manager"]
    if pm == "apt": return "sudo apt-get update -y && sudo apt-get install -y xserver-xorg-video-amdgpu mesa-vulkan-drivers libvulkan1 vulkan-tools"
    elif pm == "pacman": return "sudo pacman -S --noconfirm xf86-video-amdgpu mesa vulkan-radeon lib32-vulkan-radeon"
    elif pm in ("dnf", "yum"): return "sudo dnf install -y xorg-x11-drv-amdgpu mesa-vulkan-drivers vulkan-tools"
    return ""


def install_intel_driver() -> str:
    pm = detect_distro()["pkg_manager"]
    if pm == "apt": return "sudo apt-get update -y && sudo apt-get install -y xserver-xorg-video-intel mesa-vulkan-drivers vulkan-tools intel-media-va-driver"
    elif pm == "pacman": return "sudo pacman -S --noconfirm xf86-video-intel mesa vulkan-intel intel-media-driver"
    elif pm in ("dnf", "yum"): return "sudo dnf install -y xorg-x11-drv-intel mesa-vulkan-drivers vulkan-tools intel-media-driver"
    return ""


def get_detect_data():
    """Full GPU environment detection — single call for the detect endpoint."""
    nvidia = get_nvidia_smi_info()
    return {
        "gpus": detect_gpus(),
        "nvidia_info": nvidia[0] if nvidia else None,
        "nvidia_gpus": nvidia,
        "nvidia_detail": get_nvidia_driver_detail(),
        "nouveau": check_nouveau(),
        "display_manager": get_display_manager(),
        "kernel": get_running_kernel(),
        "kernel_headers": get_kernel_headers_path(),
        "cuda_info": get_cuda_info(),
        "secure_boot": check_secure_boot(),
        "distro": detect_distro(),
        "aur_helper": detect_aur_helper(),
        "loaded_modules": get_loaded_modules(),
    }


def get_distro_info():
    """Return distribution information (for the standalone distro endpoint)."""
    return detect_distro()
