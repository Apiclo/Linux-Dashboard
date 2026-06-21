"""CUDA toolkit configuration and installation."""
import re
import time
import urllib.request
import random
from typing import List
from utils.helpers import run_cmd
from core.distro import detect_distro, get_arch
from ._common import _version_cache, _cached, _CUDA_FALLBACK_VERSIONS


# ── User-Agent rotation pool ──
_USER_AGENTS = [
    "Linux-Toolbox/3.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "curl/8.0",
]


def _try_fetch_url(url: str, timeout: int = 20, max_attempts: int = 3) -> str:
    """Fetch a URL with exponential backoff, User-Agent rotation, and connect timeout.
    Returns the decoded response body, or raises the last exception on failure."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            ua = random.choice(_USER_AGENTS)
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
    raise last_exc  # type: ignore[misc]


def _fetch_keyring_name(repo_base_url: str) -> str:
    """Try to find the current cuda-keyring filename from the repo listing.
    Falls back to the hardcoded name if the fetch fails."""
    fallback = "cuda-keyring_1.1-1_all.deb"
    try:
        content = _try_fetch_url(repo_base_url, timeout=10)
        for line in content.splitlines():
            if "cuda-keyring" in line and ".deb" in line:
                m = re.search(r'cuda-keyring[^\s"<>]*\.deb', line)
                if m:
                    return m.group(0)
    except Exception:
        pass
    return fallback


# ── CUDA 源配置（按发行版家族） ──
CUDA_REPO_CONFIG = {
    "ubuntu": {
        "repo_base": "https://developer.download.nvidia.com/compute/cuda/repos",
        "repo_path": "ubuntu{version}/{arch}",
        "keyring_pkg": "cuda-keyring_1.1-1_all.deb",  # fallback; overridden at runtime
        "setup_cmds": [
            "wget -q {repo_base}/ubuntu{version}/{arch}/{keyring_pkg} -O /tmp/cuda-keyring.deb",
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
            "wget -q {repo_base}/debian{version}/{arch}/{keyring_pkg} -O /tmp/cuda-keyring.deb",
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
            "sudo zypper --gpg-auto-import-keys addrepo -f {repo_base}/opensuse{version}/{arch} cuda",
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


def resolve_distro_family(distro: dict) -> str:
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


def _get_nvidia_repo_url() -> str:
    """构建 NVIDIA CUDA 仓库基础 URL（用于爬取版本信息）。"""
    distro = detect_distro()
    arch = get_arch()
    family = resolve_distro_family(distro)
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
    """Scrape NVIDIA driver versions from the repo Packages index."""
    url = _get_nvidia_repo_url() + "/Packages"
    try:
        content = _try_fetch_url(url)
        seen = set()
        for line in content.splitlines():
            if line.startswith("Package: nvidia-driver-"):
                ver = line.split("nvidia-driver-")[-1].strip()
                if ver.isdigit() and ver not in seen:
                    seen.add(ver)
        return sorted(seen, key=lambda x: int(x), reverse=True)
    except Exception:
        return []


def _fetch_cuda_versions_from_pm() -> List[str]:
    """Try to discover CUDA toolkit versions from the local package manager."""
    distro = detect_distro()
    pm = distro.get("pkg_manager", "")
    seen: set = set()

    try:
        if pm == "apt":
            out, code = run_cmd("apt-cache search cuda-toolkit 2>/dev/null", timeout=15)
            if code == 0:
                for line in out.splitlines():
                    m = re.search(r'cuda-toolkit-(\d+-\d+)', line)
                    if m:
                        ver = m.group(1).replace("-", ".")
                        seen.add(ver)
        elif pm in ("dnf", "yum"):
            out, code = run_cmd(f"{pm} search cuda-toolkit 2>/dev/null", timeout=15)
            if code == 0:
                for line in out.splitlines():
                    m = re.search(r'cuda-toolkit[-\s]*(\d+[\.-]\d+)', line)
                    if m:
                        ver = m.group(1).replace("-", ".")
                        seen.add(ver)
        elif pm == "pacman":
            out, code = run_cmd("pacman -Ss cuda 2>/dev/null", timeout=15)
            if code == 0:
                for line in out.splitlines():
                    m = re.search(r'cuda[-\s]*(\d+[\.-]\d+)', line)
                    if m:
                        ver = m.group(1).replace("-", ".")
                        seen.add(ver)
        elif pm == "zypper":
            out, code = run_cmd("zypper search cuda-toolkit 2>/dev/null", timeout=15)
            if code == 0:
                for line in out.splitlines():
                    m = re.search(r'cuda-toolkit[-\s]*(\d+[\.-]\d+)', line)
                    if m:
                        ver = m.group(1).replace("-", ".")
                        seen.add(ver)
    except Exception:
        pass

    return sorted(seen, reverse=True)


def fetch_cuda_versions() -> List[str]:
    def _f():
        # 1. Try web scraping first
        url = _get_nvidia_repo_url() + "/"
        try:
            content = _try_fetch_url(url)
            seen = set()
            for line in content.splitlines():
                m = re.search(r'cuda-toolkit-(\d+-\d+)', line)
                if m:
                    ver = m.group(1).replace("-", ".")
                    if ver not in seen:
                        seen.add(ver)
            if seen:
                return sorted(seen, reverse=True)
        except Exception:
            pass

        # 2. Try package manager search as secondary source
        pm_versions = _fetch_cuda_versions_from_pm()
        if pm_versions:
            return pm_versions

        # 3. Absolute last resort: hardcoded fallback list
        return _CUDA_FALLBACK_VERSIONS
    return _cached("cuda_ver", _f)


def get_cuda_info() -> str:
    nvcc, code = run_cmd("nvcc --version 2>/dev/null")
    if code == 0 and nvcc:
        return nvcc
    smi, _ = run_cmd("nvidia-smi 2>/dev/null | grep -i 'CUDA Version'")
    return smi.strip() if smi else "CUDA 未安装"


def _check_epel() -> bool:
    """Check if EPEL is available on RHEL-based systems."""
    try:
        out, code = run_cmd("dnf repolist 2>/dev/null | grep -i epel", timeout=10)
        if code == 0 and out.strip():
            return True
        out, code = run_cmd("yum repolist 2>/dev/null | grep -i epel", timeout=10)
        if code == 0 and out.strip():
            return True
    except Exception:
        pass
    return False


def _build_cuda_fmt(version: str = "") -> dict:
    """构建 CUDA 仓库命令的格式化变量。"""
    distro = detect_distro()
    arch = get_arch()
    family = resolve_distro_family(distro)
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

    # Dynamically resolve the keyring filename for deb-based families
    keyring_pkg = cfg.get("keyring_pkg", "")
    if family in ("ubuntu", "debian") and "keyring_pkg" in cfg:
        repo_base = cfg["repo_base"]
        repo_path_fmt = cfg["repo_path"]
        keyring_url = f"{repo_base}/{repo_path_fmt.format(version=fmt_version, arch=arch)}"
        keyring_pkg = _fetch_keyring_name(keyring_url)

    result = {
        "repo_base": cfg["repo_base"],
        "version": fmt_version,
        "arch": arch,
        "packages": packages,
        "family": family,
        "cfg": cfg,
        "keyring_pkg": keyring_pkg,
    }

    # EPEL warning for RHEL family
    if family == "rhel" and not _check_epel():
        result["epel_warning"] = True

    return result


def setup_cuda_repo() -> str:
    """仅设置 CUDA 仓库源（keyring / repo 文件），不安装任何包。"""
    fmt = _build_cuda_fmt()
    cfg = fmt.pop("cfg")
    fmt.pop("family", None)
    keyring = fmt.pop("keyring_pkg", "")
    epel_warning = fmt.pop("epel_warning", False)

    setup_cmds = cfg.get("setup_cmds", [])
    if not setup_cmds:
        return "echo '该发行版无需额外设置 CUDA 源（CUDA 已在官方仓库中）'"

    cmds = []
    if epel_warning:
        cmds.append("echo 'WARNING: EPEL repository not detected. Some CUDA dependencies may require EPEL.'")
        cmds.append("echo 'Install with: sudo dnf install -y epel-release'")

    cmds.extend(sc.format(**{**fmt, "keyring_pkg": keyring}) for sc in setup_cmds)
    return " && ".join(cmds)


def install_cuda_packages(version: str = "") -> str:
    """安装 CUDA 包（前提是 setup_cuda_repo 已执行）。"""
    fmt = _build_cuda_fmt(version)
    cfg = fmt.pop("cfg")
    fmt.pop("family", None)
    fmt.pop("keyring_pkg", "")
    fmt.pop("epel_warning", False)
    return cfg["install_cmd"].format(**fmt)


def install_cuda_toolkit(method: str = "network", version: str = "") -> str:
    """生成 CUDA 完整安装命令（设置源 + 安装）。保留兼容旧调用。"""
    if method != "network":
        return "echo '请从 https://developer.nvidia.com/cuda-downloads 下载 .run 文件，然后在自定义标签页执行'"
    setup = setup_cuda_repo()
    install = install_cuda_packages(version)
    # 如果 setup 只是 echo（无需设置源），直接返回 install
    if setup.startswith("echo ") and "WARNING" not in setup:
        return install
    return f"{setup} && {install}"
