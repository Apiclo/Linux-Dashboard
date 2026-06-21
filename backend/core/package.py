"""Package management."""
import os
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote, atomic_sudo_write
from core.distro import detect_distro


COMMON_SOFTWARE = {
    "浏览器": {"firefox": {"apt": "firefox", "pacman": "firefox", "dnf": "firefox", "zypper": "firefox", "desc": "Firefox", "icon": "🌐"}, "chromium": {"apt": "chromium-browser", "pacman": "chromium", "dnf": "chromium", "zypper": "chromium", "desc": "Chromium", "icon": "🌐"}},
    "编辑器": {"vim": {"apt": "vim", "pacman": "vim", "dnf": "vim", "zypper": "vim", "desc": "Vim", "icon": "📝"}, "neovim": {"apt": "neovim", "pacman": "neovim", "dnf": "neovim", "zypper": "neovim", "desc": "Neovim", "icon": "📝"}, "vscode": {"apt": "code", "pacman": "code", "dnf": "code", "zypper": "code", "desc": "VS Code", "icon": "💻"}},
    "终端": {"alacritty": {"apt": "alacritty", "pacman": "alacritty", "dnf": "alacritty", "zypper": "alacritty", "desc": "Alacritty", "icon": "⬛"}, "tmux": {"apt": "tmux", "pacman": "tmux", "dnf": "tmux", "zypper": "tmux", "desc": "Tmux", "icon": "⬛"}},
    "多媒体": {"vlc": {"apt": "vlc", "pacman": "vlc", "dnf": "vlc", "zypper": "vlc", "desc": "VLC", "icon": "🎬"}, "mpv": {"apt": "mpv", "pacman": "mpv", "dnf": "mpv", "zypper": "mpv", "desc": "MPV", "icon": "🎬"}, "gimp": {"apt": "gimp", "pacman": "gimp", "dnf": "gimp", "zypper": "gimp", "desc": "GIMP", "icon": "🎨"}},
    "开发": {"git": {"apt": "git", "pacman": "git", "dnf": "git", "zypper": "git", "desc": "Git", "icon": "📦"}, "docker": {"apt": "docker.io", "pacman": "docker", "dnf": "docker", "zypper": "docker", "desc": "Docker", "icon": "🐳"}, "nodejs": {"apt": "nodejs", "pacman": "nodejs", "dnf": "nodejs", "zypper": "nodejs", "desc": "Node.js", "icon": "💚"}, "python3": {"apt": "python3", "pacman": "python", "dnf": "python3", "zypper": "python3", "desc": "Python 3", "icon": "🐍"}, "gcc": {"apt": "gcc", "pacman": "gcc", "dnf": "gcc", "zypper": "gcc", "desc": "GCC", "icon": "⚙"}},
    "系统": {"htop": {"apt": "htop", "pacman": "htop", "dnf": "htop", "zypper": "htop", "desc": "htop", "icon": "📊"}, "neofetch": {"apt": "neofetch", "pacman": "neofetch", "dnf": "neofetch", "zypper": "neofetch", "desc": "Neofetch", "icon": "🖥"}},
    "数据库": {"postgresql": {"apt": "postgresql", "pacman": "postgresql", "dnf": "postgresql", "zypper": "postgresql", "desc": "PostgreSQL", "icon": "🐘"}, "mariadb": {"apt": "mariadb-server", "pacman": "mariadb", "dnf": "mariadb-server", "zypper": "mariadb", "desc": "MariaDB", "icon": "🐬"}, "redis": {"apt": "redis-server", "pacman": "redis", "dnf": "redis", "zypper": "redis", "desc": "Redis", "icon": "🔴"}, "sqlite3": {"apt": "sqlite3", "pacman": "sqlite", "dnf": "sqlite", "zypper": "sqlite3", "desc": "SQLite", "icon": "🗄"}},
    "网络工具": {"curl": {"apt": "curl", "pacman": "curl", "dnf": "curl", "zypper": "curl", "desc": "cURL", "icon": "🔗"}, "wget": {"apt": "wget", "pacman": "wget", "dnf": "wget", "zypper": "wget", "desc": "Wget", "icon": "⬇"}, "nmap": {"apt": "nmap", "pacman": "nmap", "dnf": "nmap", "zypper": "nmap", "desc": "Nmap", "icon": "🔍"}, "tcpdump": {"apt": "tcpdump", "pacman": "tcpdump", "dnf": "tcpdump", "zypper": "tcpdump", "desc": "tcpdump", "icon": "📡"}, "netcat": {"apt": "netcat-openbsd", "pacman": "gnu-netcat", "dnf": "nmap-ncat", "zypper": "netcat-openbsd", "desc": "Netcat", "icon": "📨"}},
    "容器": {"podman": {"apt": "podman", "pacman": "podman", "dnf": "podman", "zypper": "podman", "desc": "Podman", "icon": "📦"}, "buildah": {"apt": "buildah", "pacman": "buildah", "dnf": "buildah", "zypper": "buildah", "desc": "Buildah", "icon": "🔧"}},
}

_INSTALL_CMDS = {
    'apt': 'sudo apt-get update -y && sudo apt-get install -y {pkgs}',
    'pacman': 'sudo pacman -S --noconfirm {pkgs}',
    'dnf': 'sudo dnf install -y {pkgs}',
    'zypper': 'sudo zypper install -y {pkgs}',
    'apk': 'sudo apk add {pkgs}',
    'xbps': 'sudo xbps-install -y {pkgs}',
    'emerge': 'sudo emerge --noreplace {pkgs}',
}
_REMOVE_CMDS = {
    'apt': 'sudo apt-get remove -y {pkgs}',
    'pacman': 'sudo pacman -Rns --noconfirm {pkgs}',
    'dnf': 'sudo dnf remove -y {pkgs}',
    'zypper': 'sudo zypper remove -y {pkgs}',
    'apk': 'sudo apk del {pkgs}',
    'xbps': 'sudo xbps-remove -y {pkgs}',
    'emerge': 'sudo emerge --deselect {pkgs}',
}


def get_pkg_manager() -> str:
    """Return the detected package manager name."""
    return detect_distro()["pkg_manager"]


def get_install_command(pkg: str) -> Tuple[str, str]:
    """Return (command, error_message) for async task execution."""
    pm = detect_distro()["pkg_manager"]
    qpkg = safe_quote(pkg)
    cmd = _INSTALL_CMDS.get(pm, '').format(pkgs=qpkg)
    return cmd, "" if cmd else f"Unsupported package manager: {pm}"


def get_remove_command(pkg: str) -> Tuple[str, str]:
    """Return (command, error_message) for async task execution."""
    pm = detect_distro()["pkg_manager"]
    qpkg = safe_quote(pkg)
    cmd = _REMOVE_CMDS.get(pm, '').format(pkgs=qpkg)
    return cmd, "" if cmd else f"Unsupported package manager: {pm}"


def search_package(query: str) -> str:
    pm = detect_distro()["pkg_manager"]
    # apk search returns "pkgname-version" format; xbps-query -Rs returns "[-] pkgname-version desc"
    cmds = {"apt": f"apt-cache search {safe_quote(query)} 2>/dev/null | head -30", "pacman": f"pacman -Ss {safe_quote(query)} 2>/dev/null | head -30", "dnf": f"dnf search {safe_quote(query)} 2>/dev/null | head -30", "zypper": f"zypper search {safe_quote(query)} 2>/dev/null | head -30", "apk": f"apk search {safe_quote(query)} 2>/dev/null | head -30", "xbps": f"xbps-query -Rs {safe_quote(query)} 2>/dev/null | head -30", "emerge": f"eix {safe_quote(query)} 2>/dev/null || emerge -s {safe_quote(query)} 2>/dev/null | head -30"}
    out, _ = run_cmd(cmds.get(pm, f"echo 'Unsupported: {pm}'"))
    return out


def search_package_structured(query: str) -> List[Dict]:
    """Search packages and return structured results."""
    pm = detect_distro()["pkg_manager"]
    raw = search_package(query)
    results: List[Dict] = []
    if pm == "apt":
        for line in raw.splitlines():
            parts = line.split(" - ", 1)
            if len(parts) >= 2:
                results.append({"name": parts[0].strip(), "description": parts[1].strip()})
            elif line.strip():
                results.append({"name": line.strip(), "description": ""})
    elif pm in ("dnf", "zypper"):
        for line in raw.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # dnf/zypper output: "pkgname.arch  version  repo" or "pkgname : description"
            parts = line_stripped.split(None, 2)
            if len(parts) >= 2:
                name = parts[0].strip()
                # strip arch suffix like .x86_64, .noarch
                if "." in name and not name.startswith("."):
                    name = name.rsplit(".", 1)[0]
                results.append({
                    "name": name,
                    "version": parts[1].strip() if len(parts) > 1 else "",
                    "description": parts[2].strip() if len(parts) > 2 else "",
                })
    elif pm == "pacman":
        for line in raw.splitlines():
            if "/" in line and not line.startswith(" "):
                parts = line.split("/", 1)
                name_ver = parts[1].split(None, 1) if len(parts) > 1 else [parts[0]]
                results.append({
                    "name": name_ver[0].strip(),
                    "version": name_ver[1].strip() if len(name_ver) > 1 else "",
                    "repo": parts[0].strip(),
                })
    elif pm == "apk":
        for line in raw.splitlines():
            line_stripped = line.strip()
            if line_stripped:
                # apk format: "pkgname-version" or "pkgname-version description"
                parts = line_stripped.split("-", 1)
                if len(parts) >= 1:
                    results.append({"name": parts[0].strip(), "description": line_stripped})
    elif pm == "xbps":
        for line in raw.splitlines():
            line_stripped = line.strip()
            if line_stripped:
                # xbps format: "[-] pkgname-version desc"
                clean = line_stripped.lstrip("[-] ").strip()
                parts = clean.split(" ", 1)
                if len(parts) >= 1:
                    results.append({"name": parts[0].strip(), "description": parts[1].strip() if len(parts) > 1 else ""})
    else:
        # General fallback: split lines
        for line in raw.splitlines():
            line_stripped = line.strip()
            if line_stripped:
                results.append({"name": line_stripped, "description": ""})
    return results


def install_package(pkg: str) -> Tuple[str, int]:
    pm = detect_distro()["pkg_manager"]
    cmd = _INSTALL_CMDS.get(pm, f"echo 'Unsupported'").format(pkgs=safe_quote(pkg))
    return run_cmd(cmd, timeout=300)


def remove_package(pkg: str) -> Tuple[str, int]:
    pm = detect_distro()["pkg_manager"]
    cmd = _REMOVE_CMDS.get(pm, f"echo 'Unsupported'").format(pkgs=safe_quote(pkg))
    return run_cmd(cmd, timeout=300)


# ── 已安装包列表 ──

_INSTALLED_PKG_CMDS = {
    "apt": "dpkg-query -W -f='${Package}|${Version}|${Status}|${Architecture}' 2>/dev/null",
    "pacman": "pacman -Q 2>/dev/null",
    "dnf": "rpm -qa --queryformat '%{NAME}|%{VERSION}-%{RELEASE}|installed|%{ARCH}\\n' 2>/dev/null",
    "zypper": "rpm -qa --queryformat '%{NAME}|%{VERSION}-%{RELEASE}|installed|%{ARCH}\\n' 2>/dev/null",
    "apk": "apk info -v 2>/dev/null",
    "xbps": "xbps-query -l 2>/dev/null",
    "emerge": "qlist -Iv 2>/dev/null || ls /var/db/pkg/*/ 2>/dev/null",
}


def get_installed_packages(filter_str: str = "", limit: int = 500) -> List[Dict]:
    """获取已安装的包列表。"""
    pm = detect_distro()["pkg_manager"]
    cmd = _INSTALLED_PKG_CMDS.get(pm, "echo 'Unsupported'")
    out, _ = run_cmd(cmd, timeout=30)
    pkgs = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            name = parts[0].strip()
            if filter_str and filter_str.lower() not in name.lower():
                continue
            pkgs.append({
                "name": name,
                "version": parts[1].strip() if len(parts) > 1 else "",
                "status": parts[2].strip() if len(parts) > 2 else "installed",
                "arch": parts[3].strip() if len(parts) > 3 else "",
            })
        elif filter_str and filter_str.lower() not in line.strip().lower():
            continue
        else:
            pkgs.append({"name": line.strip(), "version": "", "status": "installed", "arch": ""})
        if len(pkgs) >= limit:
            break

    # Append snap and flatpak packages when available
    universal_packages = []
    universal_packages.extend(get_snap_packages())
    universal_packages.extend(get_flatpak_packages())
    for upkg in universal_packages:
        if not filter_str or filter_str.lower() in upkg.get("name", "").lower():
            pkgs.append(upkg)
        if len(pkgs) >= limit:
            break

    return pkgs


# ── 软件源管理 ──

def get_repos() -> Dict:
    """获取当前软件源配置。"""
    pm = detect_distro()["pkg_manager"]
    result = {"manager": pm, "repos": [], "files": []}

    if pm == "apt":
        # list sources.list + sources.list.d
        out, _ = run_cmd("cat /etc/apt/sources.list 2>/dev/null; cat /etc/apt/sources.list.d/*.list 2>/dev/null")
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                result["repos"].append({"line": line, "file": "sources.list"})
        ls_out, _ = run_cmd("ls /etc/apt/sources.list.d/*.list 2>/dev/null")
        result["files"] = [f.strip() for f in ls_out.splitlines() if f.strip()]

    elif pm == "dnf":
        ls_out, _ = run_cmd("ls /etc/yum.repos.d/*.repo 2>/dev/null")
        result["files"] = [f.strip() for f in ls_out.splitlines() if f.strip()]
        for f in result["files"]:
            out, _ = run_cmd(f"grep -E '^\\[|^name=|^baseurl=|^enabled=' {f} 2>/dev/null")
            current = {}
            for line in out.splitlines():
                if line.startswith("["):
                    if current:
                        result["repos"].append(current)
                    current = {"name": line.strip("[]"), "file": f}
                elif current is not None:
                    for key in ("name", "baseurl", "enabled"):
                        if line.startswith(f"{key}="):
                            current[key] = line.split("=", 1)[1].strip()
            if current:
                result["repos"].append(current)

    elif pm == "zypper":
        ls_out, _ = run_cmd("ls /etc/zypp/repos.d/*.repo 2>/dev/null")
        result["files"] = [f.strip() for f in ls_out.splitlines() if f.strip()]
        for f in result["files"]:
            out, _ = run_cmd(f"grep -E '^\\[|^name=|^baseurl=|^enabled=' {f} 2>/dev/null")
            current = {}
            for line in out.splitlines():
                if line.startswith("["):
                    if current:
                        result["repos"].append(current)
                    current = {"name": line.strip("[]"), "file": f}
                elif current is not None:
                    for key in ("name", "baseurl", "enabled"):
                        if line.startswith(f"{key}="):
                            current[key] = line.split("=", 1)[1].strip()
            if current:
                result["repos"].append(current)

    elif pm == "pacman":
        out, _ = run_cmd("grep -E '^\\[' /etc/pacman.conf 2>/dev/null")
        for line in out.splitlines():
            line = line.strip().strip("[]")
            if line and line != "options":
                result["repos"].append({"name": line, "file": "/etc/pacman.conf"})

    elif pm == "apk":
        # Alpine repos: one URL per line in /etc/apk/repositories
        out, _ = run_cmd("cat /etc/apk/repositories 2>/dev/null")
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                result["repos"].append({"url": line, "file": "/etc/apk/repositories"})
        result["files"] = ["/etc/apk/repositories"] if result["repos"] else []

    elif pm == "xbps":
        # Void repos: .conf files in /etc/xbps.d/ and /usr/share/xbps.d/
        for d in ("/etc/xbps.d", "/usr/share/xbps.d"):
            ls_out, _ = run_cmd(f"ls {d}/*.conf 2>/dev/null")
            for f in ls_out.splitlines():
                f = f.strip()
                if not f:
                    continue
                result["files"].append(f)
                out, _ = run_cmd(f"cat {f} 2>/dev/null")
                for line in out.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "repository" in line:
                        result["repos"].append({"repo": line, "file": f})

    elif pm == "emerge":
        # Gentoo repos: parse /etc/portage/repos.conf/*.conf
        for d in ("/etc/portage/repos.conf", "/usr/share/portage/config/repos.conf"):
            ls_out, _ = run_cmd(f"ls {d}/*.conf 2>/dev/null")
            for f in ls_out.splitlines():
                f = f.strip()
                if not f:
                    continue
                result["files"].append(f)
                out, _ = run_cmd(f"cat {f} 2>/dev/null")
                current = {}
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("[") and current:
                        result["repos"].append(current)
                        current = {}
                    if line.startswith("["):
                        current = {"name": line.strip("[]"), "file": f}
                    elif current is not None and "=" in line:
                        k, v = line.split("=", 1)
                        current[k.strip()] = v.strip()
                if current:
                    result["repos"].append(current)

    return result


def add_repo(url: str) -> Tuple[bool, str]:
    """添加软件源。"""
    pm = detect_distro()["pkg_manager"]
    if pm == "apt":
        # 格式: deb http://... codename main
        if not url.startswith("deb "):
            return False, "APT源必须以 'deb ' 开头"
        content = url + "\n"
        path = "/etc/apt/sources.list.d/tuxtacklebox-extra.list"
        return _write_repo_file(path, content)

    elif pm == "dnf":
        out, code = run_cmd(f"sudo dnf config-manager --add-repo {safe_quote(url)} 2>&1", timeout=15)
        return code == 0, out.strip()

    elif pm == "zypper":
        out, code = run_cmd(f"sudo zypper addrepo {safe_quote(url)} 2>&1", timeout=15)
        return code == 0, out.strip()

    elif pm == "pacman":
        # 格式: [repo-name]\nServer = url
        content = url + "\n"
        path = "/etc/pacman.d/tuxtacklebox-extra"
        return _write_repo_file(path, content)

    elif pm == "apk":
        # Alpine: append URL line to /etc/apk/repositories
        out, code = run_cmd(f"sudo sh -c 'echo {safe_quote(url)} >> /etc/apk/repositories' 2>&1", timeout=5)
        return code == 0, out.strip()

    elif pm == "xbps":
        # Void: create a .conf file in /etc/xbps.d/
        repo_name = url.split("/")[-2] if "/" in url else "extra"
        content = f'repository={url}\n'
        path = f"/etc/xbps.d/tuxtacklebox-{repo_name}.conf"
        return _write_repo_file(path, content)

    elif pm == "emerge":
        # Gentoo: try eselect repository first, then layman
        out, code = run_cmd(f"sudo eselect repository add {safe_quote(url)} 2>&1", timeout=15)
        if code != 0:
            out, code = run_cmd(f"sudo layman -a {safe_quote(url)} 2>&1", timeout=15)
        return code == 0, out.strip()

    return False, f"Not supported for {pm}"


def _write_repo_file(path: str, content: str) -> Tuple[bool, str]:
    ok, msg = atomic_sudo_write(path, content)
    return ok, msg


def remove_repo_file(path: str) -> Tuple[bool, str]:
    out, code = run_cmd(f"sudo rm -f {safe_quote(path)} 2>&1", timeout=5)
    return code == 0, out.strip()


# ── 批量操作 ──

def batch_install(packages: List[str]) -> str:
    pm = detect_distro()["pkg_manager"]
    qpkgs = " ".join(safe_quote(p) for p in packages)
    return _INSTALL_CMDS.get(pm, f"echo 'Unsupported: {{pm}}'").format(pkgs=qpkgs, pm=pm)


def batch_remove(packages: List[str]) -> str:
    pm = detect_distro()["pkg_manager"]
    qpkgs = " ".join(safe_quote(p) for p in packages)
    return _REMOVE_CMDS.get(pm, f"echo 'Unsupported: {{pm}}'").format(pkgs=qpkgs, pm=pm)


def batch_update() -> str:
    pm = detect_distro()["pkg_manager"]
    cmds = {
        "apt": "sudo apt-get update -y && sudo apt-get upgrade -y",
        "pacman": "sudo pacman -Syu --noconfirm",
        "dnf": "sudo dnf update -y",
        "zypper": "sudo zypper update -y",
        "apk": "sudo apk update && sudo apk upgrade",
        "xbps": "sudo xbps-install -Syu",
        "emerge": "sudo emerge --sync && sudo emerge -uDN @world",
    }
    return cmds.get(pm, "echo 'Unsupported'")


# ── Snap / Flatpak 通用包支持 ──

def get_snap_packages() -> List[Dict]:
    """List installed snap packages."""
    out, code = run_cmd("snap list 2>/dev/null")
    if code != 0:
        return []
    pkgs = []
    for line in out.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 3:
            pkgs.append({"name": parts[0], "version": parts[1], "publisher": parts[2], "source": "snap"})
    return pkgs


def get_flatpak_packages() -> List[Dict]:
    """List installed flatpak packages."""
    out, code = run_cmd("flatpak list --columns=name,application,version 2>/dev/null")
    if code != 0:
        return []
    pkgs = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            pkgs.append({"name": parts[0], "app_id": parts[1], "version": parts[2] if len(parts) > 2 else "", "source": "flatpak"})
    return pkgs


# ── 更新历史日志 ──

_UPDATE_LOG = os.path.expanduser("~/.tuxtacklebox/update-history.log")


def get_update_history() -> List[Dict]:
    history = []
    try:
        with open(_UPDATE_LOG) as f:
            for line in f:
                line = line.strip()
                if "|" in line:
                    parts = line.split("|", 3)
                    if len(parts) >= 3:
                        history.append({"time": parts[0], "action": parts[1], "packages": parts[2], "result": parts[3] if len(parts) > 3 else ""})
    except FileNotFoundError:
        pass
    return history[-100:]  # last 100 entries


def log_update_action(action: str, packages: str, result: str) -> None:
    import datetime
    os.makedirs(os.path.dirname(_UPDATE_LOG), exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(_UPDATE_LOG, "a") as f:
            f.write(f"{timestamp}|{action}|{packages}|{result}\n")
    except Exception:
        pass


# ═══════════════════ 软件源原始文件编辑 ═══════════════════

def get_repo_raw() -> Dict:
    """获取所有源配置文件的原始内容。"""
    pm = detect_distro()["pkg_manager"]
    files: Dict[str, str] = {}
    paths: List[str] = []

    if pm == "apt":
        if os.path.isfile("/etc/apt/sources.list"):
            paths.append("/etc/apt/sources.list")
        ls_out, _ = run_cmd("ls /etc/apt/sources.list.d/*.list 2>/dev/null")
        for f in ls_out.splitlines():
            f = f.strip()
            if f and os.path.isfile(f):
                paths.append(f)
    elif pm in ("dnf", "zypper"):
        for repo_dir in ("/etc/yum.repos.d", "/etc/zypp/repos.d"):
            ls_out, _ = run_cmd(f"ls {repo_dir}/*.repo 2>/dev/null")
            for f in ls_out.splitlines():
                f = f.strip()
                if f and os.path.isfile(f):
                    paths.append(f)
    elif pm == "pacman":
        paths = ["/etc/pacman.conf"]
    elif pm == "apk":
        paths = ["/etc/apk/repositories"]
    elif pm == "xbps":
        for d in ("/etc/xbps.d", "/usr/share/xbps.d"):
            ls_out, _ = run_cmd(f"ls {d}/*.conf 2>/dev/null")
            for f in ls_out.splitlines():
                f = f.strip()
                if f and os.path.isfile(f):
                    paths.append(f)

    for p in paths:
        try:
            with open(p) as fh:
                files[p] = fh.read()
        except Exception:
            files[p] = f"[读取失败: {p}]"

    return {"manager": pm, "files": files}


def save_repo_raw(file_path: str, content: str) -> Tuple[bool, str]:
    """保存源配置文件（仅允许已知仓库配置路径）。"""
    allowed_prefixes = [
        "/etc/apt/", "/etc/yum.repos.d/", "/etc/zypp/repos.d/",
        "/etc/pacman.conf", "/etc/pacman.d/", "/etc/apk/repositories",
        "/etc/xbps.d/", "/usr/share/xbps.d/",
    ]
    real_path = os.path.realpath(os.path.expanduser(file_path))
    if not any(real_path.startswith(p) for p in allowed_prefixes):
        return False, f"不允许修改: {file_path}"

    try:
        atomic_sudo_write(real_path, content)
        return True, f"已保存: {real_path}"
    except Exception as e:
        return False, f"保存失败: {str(e)}"
