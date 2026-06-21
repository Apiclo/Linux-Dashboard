"""System rescue tools: ISO mount, local repo config, chroot preparation."""
import os
import re
from typing import Dict, List, Tuple
from urllib.parse import quote as url_quote
from utils.helpers import run_cmd, safe_quote


# ── ISO 管理 ──

def mount_iso(iso_path: str, mount_point: str) -> Tuple[str, int]:
    """挂载 ISO 到指定目录。"""
    real_iso = os.path.realpath(os.path.expanduser(iso_path))
    if not os.path.isfile(real_iso):
        return f"ISO 文件不存在: {real_iso}", -1
    real_mp = os.path.realpath(os.path.expanduser(mount_point))
    os.makedirs(real_mp, exist_ok=True)
    return run_cmd(f"sudo mount -o loop,ro {safe_quote(real_iso)} {safe_quote(real_mp)}", timeout=30)


def umount_iso(mount_point: str) -> Tuple[str, int]:
    """卸载已挂载的 ISO。"""
    real_mp = os.path.realpath(os.path.expanduser(mount_point))
    return run_cmd(f"sudo umount {safe_quote(real_mp)}", timeout=15)


def get_mounted_isos() -> List[Dict]:
    """获取当前已挂载的 ISO (loop 设备)。"""
    out, _ = run_cmd("findmnt -ln -o SOURCE,TARGET,FSTYPE 2>/dev/null | grep -E 'iso9660|udf'")
    isos = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            isos.append({"source": parts[0], "target": parts[1], "fstype": parts[2] if len(parts) > 2 else "iso9660"})
    return isos


def list_iso_content(iso_path: str) -> Tuple[List[Dict], str]:
    """列出 ISO 内容。"""
    real_iso = os.path.realpath(os.path.expanduser(iso_path))
    if not os.path.isfile(real_iso):
        return [], f"文件不存在: {real_iso}"
    # 优先用 isoinfo，其次 7z，最后 mount+ls
    out, code = run_cmd(f"isoinfo -l -i {safe_quote(real_iso)} 2>/dev/null")
    if code == 0 and out:
        items = []
        for line in out.splitlines():
            if line.startswith("Directory listing of"):
                continue
            m = re.match(r'.*\s+\[\s*(\d+)\]\s+(.+)', line)
            if m:
                items.append({"size": int(m.group(1)), "name": m.group(2).strip()})
        return items, ""
    # fallback: mount temporarily
    tmp = f"/tmp/iso_browse_{os.getpid()}"
    os.makedirs(tmp, exist_ok=True)
    _, mc = run_cmd(f"sudo mount -o loop,ro {safe_quote(real_iso)} {safe_quote(tmp)} 2>/dev/null", timeout=15)
    if mc != 0:
        return [], "无法挂载 ISO"
    out, _ = run_cmd(f"find {safe_quote(tmp)} -maxdepth 3 -type f -printf '%s %P\\n' 2>/dev/null | sort -t/ -k1,1 | head -200")
    run_cmd(f"sudo umount {safe_quote(tmp)} 2>/dev/null", timeout=10)
    rmtree_safe(tmp)
    items = []
    for line in out.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            try:
                items.append({"size": int(parts[0]), "name": parts[1].strip()})
            except ValueError:
                pass
    return items, ""


def rmtree_safe(path: str):
    try:
        os.rmdir(path)
    except OSError:
        pass


# ── 本地源配置 ──

def configure_local_repo(mount_point: str, distro_family: str) -> Tuple[bool, str]:
    """根据发行版家族配置本地软件源（指向已挂载的 ISO 目录）。"""
    real_mp = os.path.realpath(os.path.expanduser(mount_point))
    repo_url = f"file://{url_quote(real_mp)}"

    if distro_family in ("ubuntu", "debian"):
        codename = _detect_iso_codename(real_mp)
        content = f"deb [trusted=yes] {repo_url} {codename} main restricted universe multiverse\n"
        path = "/etc/apt/sources.list.d/penguinfu-iso.list"
        return _write_repo_file(path, content)

    elif distro_family in ("fedora", "rhel"):
        content = (
            f"[penguinfu-iso]\n"
            f"name=Local ISO Repository\n"
            f"baseurl={repo_url}\n"
            f"enabled=1\n"
            f"gpgcheck=0\n"
            f"metadata_expire=-1\n"
        )
        path = "/etc/yum.repos.d/penguinfu-iso.repo"
        return _write_repo_file(path, content)

    elif distro_family == "opensuse":
        out, code = run_cmd(f"sudo zypper addrepo -f {safe_quote(repo_url)} penguinfu-iso 2>&1", timeout=30)
        return code == 0, out.strip()

    elif distro_family == "arch":
        # Arch: 写入自定义 repo 到 pacman.conf
        content = (
            f"\n[penguinfu-iso]\n"
            f"SigLevel = Never\n"
            f"Server = {repo_url}\n"
        )
        out, code = run_cmd(
            f"grep -q '^\\[penguinfu-iso\\]' /etc/pacman.conf 2>/dev/null && "
            f"echo 'Repo already configured' || "
            f"(echo {safe_quote(content)} | sudo tee -a /etc/pacman.conf > /dev/null && "
            f"sudo pacman -Sy 2>&1)",
            timeout=30
        )
        return code == 0, out.strip()

    return False, f"不支持的发行版家族: {distro_family}"


def _write_repo_file(path: str, content: str) -> Tuple[bool, str]:
    """写入仓库配置文件。"""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".repo")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        out, code = run_cmd(f"sudo cp {safe_quote(tmp)} {safe_quote(path)} && sudo apt-get update -y 2>&1", timeout=60)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return code == 0, out.strip()
    except Exception as e:
        return False, str(e)


def _detect_iso_codename(mount_point: str) -> str:
    """尝试从已挂载 ISO 的 dists/ 目录检测代号。"""
    out, _ = run_cmd(f"ls {safe_quote(mount_point)}/dists/ 2>/dev/null | head -1")
    if out.strip():
        return out.strip()
    # 回退：常见代号
    for guess in ["jammy", "noble", "focal", "bookworm", "bullseye", "trixie"]:
        _, code = run_cmd(f"test -d {safe_quote(mount_point)}/dists/{guess} 2>/dev/null")
        if code == 0:
            return guess
    return "jammy"


def remove_local_repo(distro_family: str) -> Tuple[bool, str]:
    """移除本地源配置。"""
    if distro_family in ("ubuntu", "debian"):
        out, code = run_cmd(
            "sudo rm -f /etc/apt/sources.list.d/penguinfu-iso.list "
            "&& sudo apt-get update -y 2>&1", timeout=30)
        return code == 0, out.strip()

    elif distro_family in ("fedora", "rhel"):
        out, code = run_cmd("sudo rm -f /etc/yum.repos.d/penguinfu-iso.repo 2>&1", timeout=10)
        return code == 0, out.strip()

    elif distro_family == "opensuse":
        out, code = run_cmd("sudo zypper removerepo penguinfu-iso 2>&1", timeout=15)
        return code == 0, out.strip()

    elif distro_family == "arch":
        out, code = run_cmd(
            "sudo sed -i '/^\\[penguinfu-iso\\]/,/^$/d' /etc/pacman.conf "
            "&& sudo pacman -Sy 2>&1", timeout=30)
        return code == 0, out.strip()

    return False, f"不支持的发行版家族: {distro_family}"


def get_repo_status(distro_family: str) -> Dict:
    """检查本地源是否已配置。"""
    checks = {
        ("ubuntu", "debian"): ("/etc/apt/sources.list.d/penguinfu-iso.list", "apt"),
        ("fedora", "rhel"): ("/etc/yum.repos.d/penguinfu-iso.repo", "dnf"),
    }
    for families, (path, pm) in checks.items():
        if distro_family in families:
            _, code = run_cmd(f"test -f {path} 2>/dev/null")
            return {"configured": code == 0, "config_file": path, "pkg_manager": pm}

    if distro_family == "opensuse":
        out, _ = run_cmd("zypper repos 2>/dev/null | grep penguinfu-iso")
        return {"configured": "penguinfu-iso" in out, "config_file": "zypper repo", "pkg_manager": "zypper"}

    if distro_family == "arch":
        out, _ = run_cmd("grep 'penguinfu-iso' /etc/pacman.conf 2>/dev/null")
        return {"configured": bool(out.strip()), "config_file": "/etc/pacman.conf", "pkg_manager": "pacman"}

    return {"configured": False, "config_file": "", "pkg_manager": "unknown"}


# ── Chroot 准备与清理 ──

CHROOT_MOUNTS = [
    ("proc", "/proc", "-t proc"),
    ("sys", "/sys", "-t sysfs"),
    ("dev", "/dev", "--bind"),
    ("devpts", "/dev/pts", "--bind"),
    ("run", "/run", "--bind"),
]


def prepare_chroot(root: str) -> Tuple[bool, str]:
    """挂载 chroot 所需的虚拟文件系统。"""
    real_root = os.path.realpath(os.path.expanduser(root))
    if not os.path.isdir(real_root):
        return False, f"目标根目录不存在: {real_root}"
    if not os.path.isdir(os.path.join(real_root, "bin")) and not os.path.isdir(os.path.join(real_root, "usr/bin")):
        return False, f"目标目录不像是系统根 (缺少 /bin 或 /usr/bin): {real_root}"

    messages = []
    for src, target, opts in CHROOT_MOUNTS:
        abs_target = os.path.join(real_root, target.lstrip("/"))
        os.makedirs(abs_target, exist_ok=True)
        if _is_mounted(abs_target):
            messages.append(f"已挂载: {target}")
            continue
        if opts.startswith("-t"):
            out, code = run_cmd(f"sudo mount {opts} {src} {safe_quote(abs_target)} 2>&1", timeout=10)
        else:
            out, code = run_cmd(f"sudo mount {opts} {safe_quote(os.path.join('/', src))} {safe_quote(abs_target)} 2>&1", timeout=10)
        if code == 0:
            messages.append(f"挂载成功: {target}")
        else:
            messages.append(f"挂载失败: {target} → {out.strip()}")

    # 可选：复制 DNS 配置
    resolv_src = "/etc/resolv.conf"
    resolv_dst = os.path.join(real_root, "etc/resolv.conf")
    if os.path.exists(resolv_src) and not os.path.exists(resolv_dst):
        run_cmd(f"sudo cp {safe_quote(resolv_src)} {safe_quote(resolv_dst)} 2>/dev/null", timeout=5)
        messages.append("已复制 /etc/resolv.conf")

    return True, "\n".join(messages)


def teardown_chroot(root: str) -> Tuple[bool, str]:
    """逆序卸载 chroot 挂载点。"""
    real_root = os.path.realpath(os.path.expanduser(root))
    messages = []
    # 逆序卸载
    for src, target, opts in reversed(CHROOT_MOUNTS):
        abs_target = os.path.join(real_root, target.lstrip("/"))
        if not _is_mounted(abs_target):
            continue
        out, code = run_cmd(f"sudo umount {safe_quote(abs_target)} 2>&1", timeout=10)
        if code == 0:
            messages.append(f"已卸载: {target}")
        else:
            # 尝试 lazy umount
            out2, code2 = run_cmd(f"sudo umount -l {safe_quote(abs_target)} 2>&1", timeout=5)
            if code2 == 0:
                messages.append(f"已强制卸载: {target}")
            else:
                messages.append(f"卸载失败: {target} → {out.strip()}")
    return True, "\n".join(messages)


def _is_mounted(path: str) -> bool:
    """检查指定路径是否已挂载。"""
    _, code = run_cmd(f"mountpoint -q {safe_quote(path)} 2>/dev/null")
    return code == 0


def get_chroot_status(root: str) -> Dict:
    """获取 chroot 环境的挂载状态。"""
    real_root = os.path.realpath(os.path.expanduser(root))
    mounts = {}
    for src, target, opts in CHROOT_MOUNTS:
        abs_target = os.path.join(real_root, target.lstrip("/"))
        mounts[target] = _is_mounted(abs_target)
    return {
        "root": real_root,
        "exists": os.path.isdir(real_root),
        "has_bin": os.path.isdir(os.path.join(real_root, "bin")) or os.path.isdir(os.path.join(real_root, "usr/bin")),
        "mounts": mounts,
        "all_ready": all(mounts.values()),
    }
