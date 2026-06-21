"""AMD and Intel open-source driver install commands with ROCm support."""
from core.distro import detect_distro


ROCM_REPO_CONFIG = {
    "ubuntu": {
        "repo_url": "https://repo.radeon.com/amdgpu-install/latest/ubuntu/{codename}",
        "setup_cmds": [
            "wget -q https://repo.radeon.com/amdgpu-install/latest/ubuntu/{codename}/amdgpu-install.deb -O /tmp/amdgpu-install.deb",
            "sudo dpkg -i /tmp/amdgpu-install.deb",
            "sudo apt-get update -y",
        ],
        "install_cmd": "sudo amdgpu-install -y --usecase={usecase}",
    },
    "fedora": {
        "repo_url": "https://repo.radeon.com/amdgpu-install/latest/fedora/{version}",
        "setup_cmds": [
            "sudo dnf install -y https://repo.radeon.com/amdgpu-install/latest/fedora/{version}/amdgpu-install.rpm",
        ],
        "install_cmd": "sudo amdgpu-install -y --usecase={usecase}",
    },
    "rhel": {
        "repo_url": "https://repo.radeon.com/amdgpu-install/latest/rhel/{version}",
        "setup_cmds": [
            "sudo dnf install -y https://repo.radeon.com/amdgpu-install/latest/rhel/{version}/amdgpu-install.rpm",
        ],
        "install_cmd": "sudo amdgpu-install -y --usecase={usecase}",
    },
}


def _resolve_rocm_family(distro: dict) -> str:
    """Map distro info to a ROCM_REPO_CONFIG key."""
    d_id = distro.get("id", "").lower()
    d_like = distro.get("like", "").lower()
    pm = distro.get("pkg_manager", "")

    if pm == "apt":
        return "ubuntu"
    if pm in ("dnf", "yum"):
        rhel_ids = {"rhel", "centos", "rocky", "alma", "almalinux", "eurolinux", "anolis", "openEuler"}
        if d_id in rhel_ids or any(r in d_like for r in ("rhel", "centos")):
            return "rhel"
        return "fedora"
    # pacman / zypper not in ROCM_REPO_CONFIG; fall back to ubuntu docs
    return "ubuntu"


def _get_rocm_distro_params(distro: dict, family: str) -> str:
    """Return the distro-specific parameter for ROCm URL formatting
    (e.g. ubuntu codename or fedora version)."""
    if family == "ubuntu":
        # Try VERSION_CODENAME first, fall back to id
        codename = distro.get("version_codename", "")
        if not codename:
            raw = distro.get("version", "22.04")
            # crude mapping of version numbers to codenames
            codename_map = {
                "20.04": "focal", "22.04": "jammy", "23.04": "lunar",
                "23.10": "mantic", "24.04": "noble", "24.10": "oracular",
                "25.04": "plucky", "26.04": "quirky",
            }
            codename = codename_map.get(raw, "jammy")
        return codename
    else:
        raw = distro.get("version", "9")
        return raw.split(".")[0] if "." in raw else raw


def install_rocm_driver(usecase: str = "rocm") -> str:
    """Build the ROCm driver install command for the detected distro.

    usecase: 'rocm' for compute-only, 'graphics,rocm' for both graphics and compute.
    """
    distro = detect_distro()
    family = _resolve_rocm_family(distro)
    cfg = ROCM_REPO_CONFIG.get(family, ROCM_REPO_CONFIG["ubuntu"])
    param = _get_rocm_distro_params(distro, family)

    setup_cmds = [
        sc.format(
            codename=param if family == "ubuntu" else "",
            version=param if family != "ubuntu" else "",
        )
        for sc in cfg["setup_cmds"]
    ]
    install_cmd = cfg["install_cmd"].format(usecase=usecase)

    return " && ".join(setup_cmds + [install_cmd])


def install_amd_driver() -> str:
    pm = detect_distro()["pkg_manager"]
    if pm == "apt":
        return "sudo apt-get update -y && sudo apt-get install -y xserver-xorg-video-amdgpu mesa-vulkan-drivers libvulkan1 vulkan-tools"
    elif pm == "pacman":
        return "sudo pacman -S --noconfirm xf86-video-amdgpu mesa vulkan-radeon lib32-vulkan-radeon"
    elif pm in ("dnf", "yum"):
        return "sudo dnf install -y xorg-x11-drv-amdgpu mesa-vulkan-drivers vulkan-tools"
    return ""


def install_intel_driver() -> str:
    pm = detect_distro()["pkg_manager"]
    if pm == "apt":
        return "sudo apt-get update -y && sudo apt-get install -y xserver-xorg-video-intel mesa-vulkan-drivers vulkan-tools intel-media-va-driver"
    elif pm == "pacman":
        return "sudo pacman -S --noconfirm xf86-video-intel mesa vulkan-intel intel-media-driver"
    elif pm in ("dnf", "yum"):
        return "sudo dnf install -y xorg-x11-drv-intel mesa-vulkan-drivers vulkan-tools intel-media-driver"
    return ""
