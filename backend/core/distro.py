"""Distro detection."""
from utils.helpers import run_cmd


def detect_distro():
    info = {"id": "unknown", "like": "unknown", "pkg_manager": "unknown", "version": "", "pretty_name": "", "is_kylin": False, "kylin_edition": ""}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="): info["id"] = line.split("=", 1)[1].strip().strip('"').lower()
                elif line.startswith("ID_LIKE="): info["like"] = line.split("=", 1)[1].strip().strip('"').lower()
                elif line.startswith("VERSION_ID="): info["version"] = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("PRETTY_NAME="): info["pretty_name"] = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    kylin, _ = run_cmd("cat /etc/kylin-version 2>/dev/null | head -1")
    combined = (info["id"] + " " + info["like"] + " " + info["pretty_name"]).lower()
    if "kylin" in combined or kylin:
        info["is_kylin"] = True
        if "server" in combined or "server" in kylin.lower():
            info["kylin_edition"] = "server"; info["pkg_manager"] = "dnf"
        else:
            info["kylin_edition"] = "desktop"; info["pkg_manager"] = "apt"
        return info
    if "uos" in combined or "uniontech" in combined:
        info["pkg_manager"] = "apt"  # UOS Desktop uses apt
        return info
    for kws, pm in [
        (["arch", "manjaro", "endeavouros", "garuda"], "pacman"),
        (["ubuntu", "debian", "mint", "pop", "elementary", "zorin", "kali", "deepin", "uos", "ukylin", "bfsu"], "apt"),
        (["fedora", "rhel", "centos", "rocky", "alma", "ol", "nsdl", "nfs"], "dnf"),
        (["opensuse", "suse", "sles"], "zypper"),
        (["alpine"], "apk"),
        (["void"], "xbps"),
        (["gentoo"], "emerge"),
    ]:
        if any(k in combined for k in kws): info["pkg_manager"] = pm; break
    return info


def detect_aur_helper():
    for h in ["paru", "yay", "pikaur"]:
        _, code = run_cmd(f"which {h} 2>/dev/null")
        if code == 0: return h
    return None


def get_arch():
    out, _ = run_cmd("uname -m")
    return out or "x86_64"
