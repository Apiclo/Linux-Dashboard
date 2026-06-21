"""Package cleanup: orphan detection, unused dependency analysis, cache cleaning."""
import os
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote
from core.distro import detect_distro


def find_orphaned_packages() -> Dict:
    """查找孤立/不再需要的软件包。"""
    pm = detect_distro()["pkg_manager"]
    result: Dict = {"manager": pm, "orphans": [], "suggestions": []}

    if pm == "apt":
        # apt: orphan = packages that were auto-installed but no longer needed
        out, _ = run_cmd("apt-get -s autoremove 2>/dev/null | grep '^Remv' | awk '{print $2}'")
        result["orphans"] = [{"name": p, "reason": "自动安装的依赖，不再被需要"} for p in out.strip().splitlines() if p]
        # Also find residual configs
        out2, _ = run_cmd("dpkg -l 2>/dev/null | grep '^rc' | awk '{print $2}'")
        for p in out2.strip().splitlines():
            if p:
                result["orphans"].append({"name": p, "reason": "已卸载但有残留配置"})

    elif pm == "pacman":
        # Orphans = packages installed as deps but no longer required
        out, _ = run_cmd("pacman -Qdtq 2>/dev/null")
        result["orphans"] = [{"name": p, "reason": "孤立依赖（不再被其他包需要）"} for p in out.strip().splitlines() if p]
        # Find packages not in official repos
        out2, _ = run_cmd("pacman -Qm 2>/dev/null | awk '{print $1}'")
        for p in out2.strip().splitlines():
            if p:
                result["suggestions"].append({"name": p, "reason": "非官方仓库包（AUR/手动安装）"})

    elif pm in ("dnf", "zypper"):
        out, _ = run_cmd("package-cleanup --orphans 2>/dev/null | tail -n +2" if pm == "dnf" else "zypper packages --orphaned 2>/dev/null")
        for line in out.strip().splitlines():
            pkg = line.split()[0] if line.split() else ""
            if pkg:
                result["orphans"].append({"name": pkg, "reason": "孤立包（不被依赖）"})
        if pm == "dnf":
            out2, _ = run_cmd("dnf list extras 2>/dev/null | tail -n +3 | awk '{print $1}'")
            for p in out2.strip().splitlines():
                if p and "." in p:
                    result["suggestions"].append({"name": p.split(".")[0], "reason": "不在仓库中的包"})

    elif pm == "apk":
        out, _ = run_cmd("apk info -v 2>/dev/null")
        # apk doesn't have a direct orphan concept; just list manually installed
        result["suggestions"].append({"name": "all", "reason": "使用 'apk del <pkg>' 删除不需要的包"})

    return result


def clean_package_cache() -> Dict:
    """清理包管理器缓存。"""
    pm = detect_distro()["pkg_manager"]
    result: Dict = {"manager": pm, "before": "", "after": "", "freed": ""}

    cmd_map = {
        "apt": "sudo apt-get clean && sudo apt-get autoclean && sudo apt-get autoremove -y",
        "pacman": "sudo pacman -Sc --noconfirm",
        "dnf": "sudo dnf clean all",
        "zypper": "sudo zypper clean",
        "apk": "sudo apk cache clean",
    }

    cmd = cmd_map.get(pm)
    if not cmd:
        return {"manager": pm, "error": "不支持的包管理器"}

    # Get cache size before
    before_out = ""
    if pm == "apt":
        before_out, _ = run_cmd("du -sh /var/cache/apt 2>/dev/null | awk '{print $1}'")
    elif pm == "pacman":
        before_out, _ = run_cmd("du -sh /var/cache/pacman/pkg 2>/dev/null | awk '{print $1}'")

    result["before"] = before_out.strip()

    out, code = run_cmd(cmd, timeout=120)

    # Get cache size after
    if pm == "apt":
        after_out, _ = run_cmd("du -sh /var/cache/apt 2>/dev/null | awk '{print $1}'")
    elif pm == "pacman":
        after_out, _ = run_cmd("du -sh /var/cache/pacman/pkg 2>/dev/null | awk '{print $1}'")
    result["after"] = (after_out.strip() if 'after_out' in dir() else "")

    result["freed"] = out.strip()[:500] if code == 0 else f"清理完成 (exit={code})"
    return result


def get_package_files(pkg: str) -> Dict:
    """列出软件包安装的文件。"""
    pm = detect_distro()["pkg_manager"]
    result: Dict = {"package": pkg, "manager": pm, "files": []}

    cmd_map = {
        "apt": f"dpkg -L {safe_quote(pkg)} 2>/dev/null",
        "pacman": f"pacman -Ql {safe_quote(pkg)} 2>/dev/null | awk '{{print $2}}'",
        "dnf": f"rpm -ql {safe_quote(pkg)} 2>/dev/null",
        "zypper": f"rpm -ql {safe_quote(pkg)} 2>/dev/null",
        "apk": f"apk info -L {safe_quote(pkg)} 2>/dev/null",
    }

    cmd = cmd_map.get(pm)
    if cmd:
        out, _ = run_cmd(cmd)
        result["files"] = [f for f in out.strip().splitlines() if f.strip() and os.path.isfile(f)][:200]
        result["total"] = len(out.strip().splitlines())

    return result
