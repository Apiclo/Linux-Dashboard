"""Package management."""
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote
from core.distro import detect_distro


COMMON_SOFTWARE = {
    "浏览器": {"firefox": {"apt": "firefox", "pacman": "firefox", "dnf": "firefox", "zypper": "firefox", "desc": "Firefox", "icon": "🌐"}, "chromium": {"apt": "chromium-browser", "pacman": "chromium", "dnf": "chromium", "zypper": "chromium", "desc": "Chromium", "icon": "🌐"}},
    "编辑器": {"vim": {"apt": "vim", "pacman": "vim", "dnf": "vim", "zypper": "vim", "desc": "Vim", "icon": "📝"}, "neovim": {"apt": "neovim", "pacman": "neovim", "dnf": "neovim", "zypper": "neovim", "desc": "Neovim", "icon": "📝"}, "vscode": {"apt": "code", "pacman": "code", "dnf": "code", "zypper": "code", "desc": "VS Code", "icon": "💻"}},
    "终端": {"alacritty": {"apt": "alacritty", "pacman": "alacritty", "dnf": "alacritty", "zypper": "alacritty", "desc": "Alacritty", "icon": "⬛"}, "tmux": {"apt": "tmux", "pacman": "tmux", "dnf": "tmux", "zypper": "tmux", "desc": "Tmux", "icon": "⬛"}},
    "多媒体": {"vlc": {"apt": "vlc", "pacman": "vlc", "dnf": "vlc", "zypper": "vlc", "desc": "VLC", "icon": "🎬"}, "mpv": {"apt": "mpv", "pacman": "mpv", "dnf": "mpv", "zypper": "mpv", "desc": "MPV", "icon": "🎬"}, "gimp": {"apt": "gimp", "pacman": "gimp", "dnf": "gimp", "zypper": "gimp", "desc": "GIMP", "icon": "🎨"}},
    "开发": {"git": {"apt": "git", "pacman": "git", "dnf": "git", "zypper": "git", "desc": "Git", "icon": "📦"}, "docker": {"apt": "docker.io", "pacman": "docker", "dnf": "docker", "zypper": "docker", "desc": "Docker", "icon": "🐳"}, "nodejs": {"apt": "nodejs", "pacman": "nodejs", "dnf": "nodejs", "zypper": "nodejs", "desc": "Node.js", "icon": "💚"}, "python3": {"apt": "python3", "pacman": "python", "dnf": "python3", "zypper": "python3", "desc": "Python 3", "icon": "🐍"}, "gcc": {"apt": "gcc", "pacman": "gcc", "dnf": "gcc", "zypper": "gcc", "desc": "GCC", "icon": "⚙"}},
    "系统": {"htop": {"apt": "htop", "pacman": "htop", "dnf": "htop", "zypper": "htop", "desc": "htop", "icon": "📊"}, "neofetch": {"apt": "neofetch", "pacman": "neofetch", "dnf": "neofetch", "zypper": "neofetch", "desc": "Neofetch", "icon": "🖥"}},
}


def get_pkg_manager() -> str:
    """Return the detected package manager name."""
    return detect_distro()["pkg_manager"]


def get_install_command(pkg: str) -> Tuple[str, str]:
    """Return (command, error_message) for async task execution."""
    pm = detect_distro()["pkg_manager"]
    qpkg = safe_quote(pkg)
    cmds = {
        "apt": f"sudo apt-get update -y && sudo apt-get install -y {qpkg}",
        "pacman": f"sudo pacman -S --noconfirm {qpkg}",
        "dnf": f"sudo dnf install -y {qpkg}",
        "zypper": f"sudo zypper install -y {qpkg}",
        "apk": f"sudo apk add {qpkg}",
        "xbps": f"sudo xbps-install -y {qpkg}",
    }
    cmd = cmds.get(pm, "")
    return cmd, "" if cmd else f"Unsupported package manager: {pm}"


def get_remove_command(pkg: str) -> Tuple[str, str]:
    """Return (command, error_message) for async task execution."""
    pm = detect_distro()["pkg_manager"]
    qpkg = safe_quote(pkg)
    cmds = {
        "apt": f"sudo apt-get remove -y {qpkg}",
        "pacman": f"sudo pacman -Rns --noconfirm {qpkg}",
        "dnf": f"sudo dnf remove -y {qpkg}",
        "zypper": f"sudo zypper remove -y {qpkg}",
        "apk": f"sudo apk del {qpkg}",
        "xbps": f"sudo xbps-remove -y {qpkg}",
    }
    cmd = cmds.get(pm, "")
    return cmd, "" if cmd else f"Unsupported package manager: {pm}"


def search_package(query: str) -> str:
    pm = detect_distro()["pkg_manager"]
    cmds = {"apt": f"apt-cache search {safe_quote(query)} 2>/dev/null | head -30", "pacman": f"pacman -Ss {safe_quote(query)} 2>/dev/null | head -30", "dnf": f"dnf search {safe_quote(query)} 2>/dev/null | head -30", "zypper": f"zypper search {safe_quote(query)} 2>/dev/null | head -30", "apk": f"apk search {safe_quote(query)} 2>/dev/null | head -30", "xbps": f"xbps-query -Rs {safe_quote(query)} 2>/dev/null | head -30"}
    out, _ = run_cmd(cmds.get(pm, f"echo 'Unsupported: {pm}'"))
    return out


def install_package(pkg: str) -> Tuple[str, int]:
    pm = detect_distro()["pkg_manager"]
    cmds = {"apt": f"sudo apt-get update -y && sudo apt-get install -y {safe_quote(pkg)}", "pacman": f"sudo pacman -S --noconfirm {safe_quote(pkg)}", "dnf": f"sudo dnf install -y {safe_quote(pkg)}", "zypper": f"sudo zypper install -y {safe_quote(pkg)}", "apk": f"sudo apk add {safe_quote(pkg)}", "xbps": f"sudo xbps-install -y {safe_quote(pkg)}"}
    return run_cmd(cmds.get(pm, f"echo 'Unsupported'"), timeout=300)


def remove_package(pkg: str) -> Tuple[str, int]:
    pm = detect_distro()["pkg_manager"]
    cmds = {"apt": f"sudo apt-get remove -y {safe_quote(pkg)}", "pacman": f"sudo pacman -Rns --noconfirm {safe_quote(pkg)}", "dnf": f"sudo dnf remove -y {safe_quote(pkg)}", "zypper": f"sudo zypper remove -y {safe_quote(pkg)}", "apk": f"sudo apk del {safe_quote(pkg)}", "xbps": f"sudo xbps-remove -y {safe_quote(pkg)}"}
    return run_cmd(cmds.get(pm, f"echo 'Unsupported'"), timeout=300)
