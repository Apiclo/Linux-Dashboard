"""System rescue tools: ISO mount, local repo config, chroot preparation, backup/restore."""
import os
import re
import time
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote, atomic_sudo_write


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
            isos.append({
                "source": parts[0],
                "target": " ".join(parts[1:-1]) if len(parts) > 2 else parts[1],
                "fstype": parts[-1] if len(parts) > 2 else "iso9660",
            })
    return isos


def list_iso_content(mount_point: str) -> List[str]:
    """列出 ISO 挂载目录内容。"""
    real_mp = os.path.realpath(os.path.expanduser(mount_point))
    if not os.path.isdir(real_mp):
        return [f"[挂载点不存在: {real_mp}]"]
    try:
        return sorted(os.listdir(real_mp))[:100]
    except PermissionError:
        return ["[权限不足]"]


# ── 本地仓库配置 ──

def configure_local_repo(mount_point: str, distro_family: str) -> Tuple[str, int]:
    """配置本地 ISO 仓库。"""
    real_mp = os.path.realpath(os.path.expanduser(mount_point))

    if distro_family in ("debian", "ubuntu", "kylin", "uos"):
        repo_line = f"deb [trusted=yes] file:{real_mp} ./"
        repo_file = "/etc/apt/sources.list.d/local-iso.list"
    elif distro_family in ("rhel", "centos", "fedora", "openEuler"):
        repo_id = os.path.basename(real_mp.rstrip("/")) or "local-iso"
        repo_content = f"""[{repo_id}]
name=Local ISO Repository
baseurl=file://{real_mp}
enabled=1
gpgcheck=0
"""
        repo_file = f"/etc/yum.repos.d/{repo_id}.repo"
        return atomic_sudo_write(repo_file, repo_content)
    elif distro_family == "arch":
        repo_line = f"\n[{os.path.basename(real_mp.rstrip('/')) or 'local'}]\nSigLevel = Never\nServer = file://{real_mp}\n"
        repo_file = "/etc/pacman.conf"
        # Append to pacman.conf
        out, code = run_cmd(
            f"sudo bash -c 'echo {safe_quote(repo_line)} >> {safe_quote(repo_file)}'",
            timeout=10
        )
        return out, code
    elif distro_family in ("suse", "opensuse"):
        repo_id = os.path.basename(real_mp.rstrip("/")) or "local-iso"
        return run_cmd(
            f"sudo zypper addrepo -f 'file://{real_mp}' {safe_quote(repo_id)}",
            timeout=15
        )
    else:
        return f"不支持的发行版类型: {distro_family}", -1

    return atomic_sudo_write(repo_file, repo_line)


def remove_local_repo(distro_family: str) -> Tuple[str, int]:
    """移除本地 ISO 仓库配置。"""
    if distro_family in ("debian", "ubuntu", "kylin", "uos"):
        return run_cmd("sudo rm -f /etc/apt/sources.list.d/local-iso.list && sudo apt-get update", timeout=30)
    elif distro_family in ("rhel", "centos", "fedora", "openEuler"):
        return run_cmd("sudo rm -f /etc/yum.repos.d/local-iso.repo", timeout=10)
    elif distro_family == "arch":
        return run_cmd("sudo sed -i '/^\\[local\\]/,/^Server = file:/d' /etc/pacman.conf", timeout=10)
    elif distro_family in ("suse", "opensuse"):
        return run_cmd("sudo zypper removerepo local-iso", timeout=15)
    return "未知发行版", -1


def get_repo_status() -> Dict:
    """获取本地仓库状态。"""
    result = {"active": False, "files": []}
    patterns = [
        "/etc/apt/sources.list.d/local-iso.list",
        "/etc/yum.repos.d/local-iso.repo",
        "/etc/yum.repos.d/*.repo",
    ]
    for pattern in patterns:
        import glob
        for f in glob.glob(pattern):
            if os.path.isfile(f):
                try:
                    with open(f) as fh:
                        if "file:/" in fh.read():
                            result["active"] = True
                            result["files"].append(f)
                except Exception:
                    pass
    # Check pacman.conf for local repo
    try:
        with open("/etc/pacman.conf") as fh:
            content = fh.read()
            if "[local]" in content and "file://" in content:
                result["active"] = True
                result["files"].append("/etc/pacman.conf")
    except Exception:
        pass
    return result


# ── Chroot 管理 ──

_MOUNT_PSEUDOFS = [
    ("/proc", "proc", "-t proc"),
    ("/sys", "sysfs", "-t sysfs"),
    ("/dev", "devtmpfs", "-t devtmpfs"),
    ("/dev/pts", "devpts", "-t devpts"),
    ("/run", "tmpfs", "-t tmpfs"),
]


def prepare_chroot(root: str) -> List[Dict]:
    """准备 chroot 环境。返回每步结果。"""
    real_root = os.path.realpath(os.path.expanduser(root))
    if not os.path.isdir(real_root):
        return [{"target": root, "success": False, "message": "目标路径不存在或不是目录"}]

    results = []
    for target, _, opts in _MOUNT_PSEUDOFS:
        full = os.path.join(real_root, target.lstrip("/"))
        os.makedirs(full, exist_ok=True)
        # Check if already mounted
        check_out, _ = run_cmd(f"mountpoint -q {safe_quote(full)} 2>/dev/null")
        if check_out is not None:
            # Not mounted - proceed
            out, code = run_cmd(f"sudo mount {opts} {target} {safe_quote(full)} 2>&1", timeout=10)
            results.append({
                "target": target,
                "mounted": code == 0,
                "message": "已挂载" if code == 0 else out.strip(),
            })
        else:
            results.append({"target": target, "mounted": True, "message": "已挂载 (已存在)"})
    return results


def teardown_chroot(root: str) -> List[Dict]:
    """拆卸 chroot 环境。"""
    real_root = os.path.realpath(os.path.expanduser(root))
    results = []
    for target, _, _ in reversed(_MOUNT_PSEUDOFS):
        full = os.path.join(real_root, target.lstrip("/"))
        out, code = run_cmd(f"sudo umount {safe_quote(full)} 2>&1", timeout=10)
        results.append({
            "target": target,
            "mounted": code != 0,  # True if still mounted (failed to unmount)
            "message": "已卸载" if code == 0 else out.strip(),
        })
    return results


def get_chroot_status(root: str) -> List[Dict]:
    """获取 chroot 挂载状态。"""
    real_root = os.path.realpath(os.path.expanduser(root))
    results = []
    for target, name, _ in _MOUNT_PSEUDOFS:
        full = os.path.join(real_root, target.lstrip("/"))
        out, _ = run_cmd(f"mountpoint -q {safe_quote(full)} 2>/dev/null")
        mounted = out is None  # mountpoint returns 0 if mounted
        results.append({"target": target, "name": name, "mounted": mounted})
    return results


# ── SFTP 管理 ──

def check_sshfs() -> Tuple[bool, str]:
    """检查 sshfs 是否可用。"""
    _, code = run_cmd("which sshfs 2>/dev/null")
    if code != 0:
        return False, "sshfs 未安装。安装: apt install sshfs 或 pacman -S sshfs"
    return True, "sshfs 可用"


def mount_sftp(user: str, host: str, port: int, remote_path: str, mount_point: str,
               key_file: str = "", reconnect: bool = False) -> Tuple[str, int]:
    """挂载 SFTP 远程目录。"""
    # 参数验证
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9._-]*$', user):
        return f"无效的用户名: {user}", -1
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', host) and not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
        return f"无效的主机名: {host}", -1
    try:
        port = int(port)
        if not (1 <= port <= 65535):
            raise ValueError
    except (ValueError, TypeError):
        return f"无效的端口号: {port}", -1

    remote_path = remote_path.strip() or "/"
    if not remote_path.startswith("/"):
        remote_path = "/" + remote_path

    real_mp = os.path.realpath(os.path.expanduser(mount_point))
    if not real_mp.startswith("/"):
        return f"挂载点必须是绝对路径: {mount_point}", -1
    os.makedirs(real_mp, exist_ok=True)

    # SSH 密钥权限检查
    key_opts = ""
    if key_file:
        real_key = os.path.realpath(os.path.expanduser(key_file))
        if os.path.exists(real_key):
            key_stat = os.stat(real_key)
            key_mode = key_stat.st_mode & 0o777
            if key_mode != 0o600:
                return f"SSH 密钥权限不安全 ({oct(key_mode)}), 需为 600 (chmod 600 {real_key})", -1
            key_opts = f"-o IdentityFile={safe_quote(real_key)}"

    reconnect_opts = "-o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ConnectTimeout=10" if reconnect else ""
    remote = f"{user}@{host}:{remote_path}"

    return run_cmd(
        f"sudo sshfs {remote} {safe_quote(real_mp)} "
        f"-p {port} -o allow_other,default_permissions "
        f"{key_opts} {reconnect_opts} 2>&1",
        timeout=30
    )


def umount_sftp(mount_point: str) -> Tuple[str, int]:
    """卸载 SFTP 挂载。"""
    real_mp = os.path.realpath(os.path.expanduser(mount_point))
    return run_cmd(f"sudo umount {safe_quote(real_mp)}", timeout=15)


def get_sftp_mounts() -> List[Dict]:
    """获取当前已挂载的 sshfs 连接。"""
    out, _ = run_cmd("mount -t fuse.sshfs 2>/dev/null")
    mounts = []
    for line in out.splitlines():
        if "fuse.sshfs" not in line and "sshfs" not in line:
            continue
        parts = line.split()
        if len(parts) >= 3:
            mounts.append({
                "source": parts[0].replace(f"@{parts[0].split('@')[0]}:", "@...:") if "@" in parts[0] else parts[0],
                "target": parts[2],
                "fstype": "fuse.sshfs",
                "source_full": parts[0],
            })
    return mounts


def list_directory(path: str) -> List[Dict]:
    """列出目录内容，含文件类型、大小、权限。"""
    real_path = os.path.realpath(os.path.expanduser(path))
    if not os.path.isdir(real_path):
        return [{"name": os.path.basename(real_path), "type": "error", "size": 0, "mode": "", "mtime": "", "error": "路径不存在"}]
    items = []
    try:
        for entry in sorted(os.scandir(real_path), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                stat = entry.stat()
            except OSError:
                stat = None
            items.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else ("link" if entry.is_symlink() else "file"),
                "size": stat.st_size if stat and not entry.is_dir() else 0,
                "mode": oct(stat.st_mode)[-3:] if stat else "???",
                "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)) if stat else "",
            })
    except PermissionError:
        items.append({"name": ".", "type": "error", "size": 0, "mode": "", "mtime": "", "error": "权限不足"})
    return items


# ══════════════════════════════════════════════════════════════
#  系统备份 / 恢复 (NEW)
# ══════════════════════════════════════════════════════════════

BACKUP_DIR = os.path.expanduser("~/.tuxtacklebox/backups")


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def create_system_snapshot(name: str = "", include_home: bool = False) -> Dict:
    """创建系统快照，包含系统配置、包列表、分区表等。

    Args:
        name: 快照名称（可选，默认用时间戳）。
        include_home: 是否包含 /home 目录。
    """
    _ensure_backup_dir()
    ts = time.strftime("%Y%m%d_%H%M%S")
    snap_name = name.strip().replace(" ", "_") if name.strip() else f"snapshot_{ts}"
    snap_dir = os.path.join(BACKUP_DIR, snap_name)
    os.makedirs(snap_dir, exist_ok=True)

    collected: Dict[str, str] = {}
    errors: List[str] = []

    # 1. 包列表
    from core.distro import detect_distro
    pm = detect_distro()["pkg_manager"]
    if pm == "apt":
        out, _ = run_cmd("dpkg -l 2>/dev/null | grep '^ii' | awk '{print $2, $3}'")
    elif pm == "pacman":
        out, _ = run_cmd("pacman -Q 2>/dev/null")
    elif pm == "dnf":
        out, _ = run_cmd("rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE}\n' 2>/dev/null")
    elif pm == "zypper":
        out, _ = run_cmd("rpm -qa --qf '%{NAME} %{VERSION}\n' 2>/dev/null")
    elif pm == "apk":
        out, _ = run_cmd("apk info -v 2>/dev/null")
    else:
        out = ""
    if out.strip():
        collected["packages.txt"] = out
    else:
        errors.append("无法获取包列表")

    # 2. 分区布局
    out, _ = run_cmd("sudo fdisk -l 2>/dev/null")
    if out.strip():
        collected["partitions.txt"] = out
    out2, _ = run_cmd("sudo blkid 2>/dev/null")
    if out2.strip():
        collected["blkid.txt"] = out2

    # 3. fstab
    try:
        with open("/etc/fstab") as f:
            collected["fstab"] = f.read()
    except Exception:
        errors.append("无法读取 /etc/fstab")

    # 4. 关键系统配置
    config_files = [
        "/etc/hostname", "/etc/hosts", "/etc/resolv.conf",
        "/etc/ssh/sshd_config", "/etc/sysctl.conf",
        "/etc/default/grub", "/etc/security/limits.conf",
        "/etc/systemd/journald.conf", "/etc/motd",
        "/etc/pacman.conf", "/etc/apt/sources.list",
        "/etc/fstab", "/etc/crypttab",
    ]
    for cf in config_files:
        if os.path.isfile(cf):
            try:
                with open(cf) as f:
                    key = cf.lstrip("/").replace("/", "_")
                    collected[key] = f.read()
            except Exception:
                pass

    # 5. 网络配置
    netplan_dir = "/etc/netplan"
    if os.path.isdir(netplan_dir):
        for nf in os.listdir(netplan_dir):
            nfp = os.path.join(netplan_dir, nf)
            if os.path.isfile(nfp):
                try:
                    with open(nfp) as f:
                        collected[f"netplan_{nf}"] = f.read()
                except Exception:
                    pass

    # 6. systemd 服务状态
    out, _ = run_cmd("systemctl list-unit-files --type=service --state=enabled 2>/dev/null | head -50")
    if out.strip():
        collected["enabled_services.txt"] = out

    # 7. 内核模块
    out, _ = run_cmd("lsmod 2>/dev/null | head -50")
    if out.strip():
        collected["loaded_modules.txt"] = out

    # 8. 用户列表
    out, _ = run_cmd("awk -F: '$3>=1000 && $3<65534 {print $1, $3, $6, $7}' /etc/passwd 2>/dev/null")
    if out.strip():
        collected["users.txt"] = out

    # 9. 写入文件
    for filename, content in collected.items():
        filepath = os.path.join(snap_dir, filename)
        try:
            with open(filepath, 'w') as f:
                f.write(content)
        except Exception as e:
            errors.append(f"写入 {filename} 失败: {e}")

    # 10. /home 备份（可选）
    if include_home:
        home_archive = os.path.join(snap_dir, "home_backup.tar.gz")
        out, code = run_cmd(
            f"sudo tar -czf {safe_quote(home_archive)} --exclude='.cache' --exclude='node_modules' "
            f"--exclude='.npm' --exclude='.cargo' -C / home 2>&1",
            timeout=600
        )
        if code != 0:
            errors.append(f"Home 备份失败: {out[:200]}")

    # 11. 创建清单
    manifest = {
        "name": snap_name,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": int(time.time()),
        "files": list(collected.keys()),
        "include_home": include_home,
        "package_manager": pm,
        "hostname": os.uname().nodename,
        "errors": errors,
    }
    import json
    manifest_path = os.path.join(snap_dir, "manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return {
        "success": len(collected) > 3,
        "name": snap_name,
        "path": snap_dir,
        "file_count": len(collected),
        "errors": errors,
    }


def list_snapshots() -> List[Dict]:
    """列出所有快照。"""
    _ensure_backup_dir()
    snapshots = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        path = os.path.join(BACKUP_DIR, name)
        if not os.path.isdir(path):
            continue
        manifest_path = os.path.join(path, "manifest.json")
        manifest = {}
        if os.path.isfile(manifest_path):
            import json
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
            except json.JSONDecodeError:
                pass
        # Count actual files
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        snapshots.append({
            "name": name,
            "path": path,
            "created": manifest.get("created", "未知"),
            "timestamp": manifest.get("timestamp", 0),
            "file_count": len(files),
            "include_home": manifest.get("include_home", False),
            "hostname": manifest.get("hostname", ""),
            "errors": manifest.get("errors", []),
        })
    return snapshots


def delete_snapshot(name: str) -> Tuple[bool, str]:
    """删除指定快照。"""
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', name):
        return False, f"无效的快照名称: {name}"
    snap_dir = os.path.join(BACKUP_DIR, name)
    if not os.path.isdir(snap_dir):
        return False, f"快照不存在: {name}"
    import shutil
    try:
        shutil.rmtree(snap_dir)
        return True, f"已删除快照: {name}"
    except Exception as e:
        return False, f"删除失败: {str(e)}"


def restore_config_file(snapshot: str, filename: str) -> Tuple[bool, str]:
    """从快照中恢复单个配置文件。"""
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', snapshot):
        return False, f"无效的快照名称: {snapshot}"
    snap_dir = os.path.join(BACKUP_DIR, snapshot)
    src = os.path.join(snap_dir, filename)
    if not os.path.isfile(src):
        return False, f"快照中未找到文件: {filename}"

    # Map snapshot filename back to system path
    path_map = {
        "fstab": "/etc/fstab",
        "etc_hostname": "/etc/hostname",
        "etc_hosts": "/etc/hosts",
        "etc_resolv.conf": "/etc/resolv.conf",
        "etc_ssh_sshd_config": "/etc/ssh/sshd_config",
        "etc_sysctl.conf": "/etc/sysctl.conf",
        "etc_default_grub": "/etc/default/grub",
        "etc_security_limits.conf": "/etc/security/limits.conf",
        "etc_systemd_journald.conf": "/etc/systemd/journald.conf",
        "etc_motd": "/etc/motd",
    }
    dest = path_map.get(filename)
    if not dest:
        # Fallback: try original filename if it exists
        potential = "/" + filename.replace("_", "/").replace("etc/", "/etc/", 1)
        if os.path.exists(os.path.dirname(potential)):
            dest = potential
        else:
            return False, f"无法确定 {filename} 的目标路径"

    try:
        with open(src) as f:
            content = f.read()
        return atomic_sudo_write(dest, content), "已恢复"
    except Exception as e:
        return False, f"恢复失败: {str(e)}"


def compare_snapshot(name: str) -> Dict:
    """比较快照与当前系统状态。"""
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', name):
        return {"error": f"无效的快照名称: {name}"}
    snap_dir = os.path.join(BACKUP_DIR, name)
    if not os.path.isdir(snap_dir):
        return {"error": f"快照不存在: {name}"}

    diffs = []
    compare_files = [
        ("fstab", "/etc/fstab"),
        ("etc_hostname", "/etc/hostname"),
        ("etc_hosts", "/etc/hosts"),
        ("etc_ssh_sshd_config", "/etc/ssh/sshd_config"),
        ("etc_default_grub", "/etc/default/grub"),
    ]

    for snap_file, sys_path in compare_files:
        snap_path = os.path.join(snap_dir, snap_file)
        status = "missing"
        if os.path.isfile(snap_path):
            try:
                with open(snap_path) as f:
                    snap_content = f.read()
                if os.path.isfile(sys_path):
                    with open(sys_path) as f:
                        sys_content = f.read()
                    status = "same" if snap_content == sys_content else "changed"
                else:
                    status = "deleted"
            except Exception:
                status = "error"
        else:
            status = "not_in_snapshot"
        if status != "same":
            diffs.append({"file": sys_path, "status": status})

    # Compare installed packages
    snap_pkg = os.path.join(snap_dir, "packages.txt")
    if os.path.isfile(snap_pkg):
        from core.distro import detect_distro
        pm = detect_distro()["pkg_manager"]
        if pm == "pacman":
            current, _ = run_cmd("pacman -Q 2>/dev/null")
        elif pm == "apt":
            current, _ = run_cmd("dpkg -l 2>/dev/null | grep '^ii' | awk '{print $2, $3}'")
        elif pm == "dnf":
            current, _ = run_cmd("rpm -qa --qf '%{NAME} %{VERSION}\n' 2>/dev/null")
        else:
            current = ""
        with open(snap_pkg) as f:
            snap_pkg_list = set(f.read().strip().splitlines())
        current_pkg_list = set(current.strip().splitlines())
        added = current_pkg_list - snap_pkg_list
        removed = snap_pkg_list - current_pkg_list
        if added:
            diffs.append({"file": "packages", "status": f"+{len(added)} 新增"})
        if removed:
            diffs.append({"file": "packages", "status": f"-{len(removed)} 移除"})

    return {"name": name, "diffs": diffs}
