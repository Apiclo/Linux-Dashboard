"""System rescue routes: ISO management + chroot."""
import os
from typing import List, Tuple
from flask import Blueprint, jsonify, request, session
from utils.helpers import safe_api, validate_json, require_auth, run_cmd, safe_quote, safe_temp_file
from utils.tasks import start_task
from core import rescue, distro

bp = Blueprint("rescue", __name__)

ALLOWED_MOUNT_PREFIXES = ["/mnt/", "/media/", "/srv/"]
ALLOWED_CHROOT_PREFIXES = ["/mnt/", "/media/"]


def _validate_mount_path(p: str, prefixes: List[str]) -> Tuple[bool, str]:
    """校验挂载/chroot 路径在允许的前缀下。"""
    real = os.path.realpath(os.path.expanduser(p))
    for prefix in prefixes:
        if real == prefix.rstrip("/") or real.startswith(prefix):
            return True, real
    return False, f"路径不允许: {real}（仅允许 {' / '.join(prefixes)}）"


# ═══════════════════ ISO 管理 ═══════════════════

@bp.route("/api/rescue/iso/mount", methods=["POST"])
@safe_api
@require_auth
@validate_json(["iso_path", "mount_point"])
def iso_mount(data):
    """挂载 ISO 并可选配置本地源。"""
    ok_iso, real_iso = _validate_mount_path(data["iso_path"], ALLOWED_MOUNT_PREFIXES + ["/home/", "/data/", "/opt/", "/tmp/", "/var/"])
    ok_mp, real_mp = _validate_mount_path(data["mount_point"], ALLOWED_MOUNT_PREFIXES)
    if not ok_mp:
        return jsonify({"success": False, "message": real_mp}), 400
    configure = data.get("configure_repo", False)

    out, code = rescue.mount_iso(real_iso if ok_iso else data["iso_path"], real_mp)
    if code != 0:
        return jsonify({"success": False, "message": out})

    result = {"success": True, "message": f"ISO 已挂载到 {real_mp}"}

    if configure:
        d = distro.detect_distro()
        from core.gpu import resolve_distro_family
        family = resolve_distro_family(d)
        ok, msg = rescue.configure_local_repo(real_mp, family)
        result["repo_configured"] = ok
        result["repo_message"] = msg
        result["distro_family"] = family

    return jsonify(result)


@bp.route("/api/rescue/iso/umount", methods=["POST"])
@safe_api
@require_auth
@validate_json(["mount_point"])
def iso_umount(data):
    ok, mp = _validate_mount_path(data["mount_point"], ALLOWED_MOUNT_PREFIXES)
    if not ok:
        return jsonify({"success": False, "message": mp}), 400
    remove_repo = data.get("remove_repo", True)

    if remove_repo:
        d = distro.detect_distro()
        from core.gpu import resolve_distro_family
        family = resolve_distro_family(d)
        rescue.remove_local_repo(family)

    out, code = rescue.umount_iso(mp)
    # 清理空挂载点
    run_cmd(f"sudo rmdir {safe_quote(mp)} 2>/dev/null", timeout=5)
    return jsonify({"success": code == 0, "message": out or "已卸载"})


@bp.route("/api/rescue/iso/list", methods=["POST"])
@safe_api
@require_auth
@validate_json(["iso_path"])
def iso_list(data):
    items, err = rescue.list_iso_content(data["iso_path"])
    return jsonify({"success": not bool(err), "items": items, "message": err})


@bp.route("/api/rescue/iso/mounted")
@safe_api
@require_auth
def iso_mounted():
    return jsonify({"isos": rescue.get_mounted_isos()})


@bp.route("/api/rescue/iso/repo-status")
@safe_api
@require_auth
def iso_repo_status():
    d = distro.detect_distro()
    from core.gpu import resolve_distro_family
    family = resolve_distro_family(d)
    return jsonify(rescue.get_repo_status(family))


@bp.route("/api/rescue/iso/remove-repo", methods=["POST"])
@safe_api
@require_auth
def iso_remove_repo():
    d = distro.detect_distro()
    from core.gpu import resolve_distro_family
    family = resolve_distro_family(d)
    ok, msg = rescue.remove_local_repo(family)
    return jsonify({"success": ok, "message": msg})


# ═══════════════════ Chroot 管理 ═══════════════════

@bp.route("/api/rescue/chroot/prepare", methods=["POST"])
@safe_api
@require_auth
@validate_json(["root"])
def chroot_prepare(data):
    ok_root, root = _validate_mount_path(data["root"], ALLOWED_CHROOT_PREFIXES)
    if not ok_root:
        return jsonify({"success": False, "message": root}), 400
    ok, msg = rescue.prepare_chroot(root)
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/rescue/chroot/teardown", methods=["POST"])
@safe_api
@require_auth
@validate_json(["root"])
def chroot_teardown(data):
    ok_root, root = _validate_mount_path(data["root"], ALLOWED_CHROOT_PREFIXES)
    if not ok_root:
        return jsonify({"success": False, "message": root}), 400
    ok, msg = rescue.teardown_chroot(root)
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/rescue/chroot/status")
@safe_api
@require_auth
def chroot_status():
    ok, root = _validate_mount_path(request.args.get("root", "/mnt").strip(), ALLOWED_CHROOT_PREFIXES)
    if not ok:
        return jsonify({"success": False, "message": root}), 400
    return jsonify(rescue.get_chroot_status(root))


@bp.route("/api/rescue/chroot/exec", methods=["POST"])
@safe_api
@require_auth
@validate_json(["root", "command"])
def chroot_exec(data):
    """在 chroot 环境中执行单条命令（非交互）。"""
    ok, root = _validate_mount_path(data["root"], ALLOWED_CHROOT_PREFIXES)
    if not ok:
        return jsonify({"success": False, "message": root}), 400
    cmd = data["command"]
    if not cmd.strip():
        return jsonify({"success": False, "message": "Command required"}), 400
    if len(cmd) > 4000:
        return jsonify({"success": False, "message": "Command too long"}), 400
    # 将命令写入临时脚本，避免 bash -c 注入风险
    tmp = safe_temp_file(content=cmd)
    out, code = run_cmd(
        f"sudo cp {safe_quote(tmp)} {safe_quote(root)}/tmp/_tuxtacklebox_cmd.sh && "
        f"sudo chroot {safe_quote(root)} /bin/bash /tmp/_tuxtacklebox_cmd.sh",
        timeout=30
    )
    run_cmd(f"sudo rm -f {safe_quote(root)}/tmp/_tuxtacklebox_cmd.sh 2>/dev/null", timeout=5)
    return jsonify({"success": code == 0, "output": out, "exit_code": code})


# ═══════════════════ SFTP 挂载 ═══════════════════

@bp.route("/api/rescue/sftp/check")
@safe_api
@require_auth
def sftp_check():
    ok, msg = rescue.check_sshfs()
    return jsonify({"available": ok, "message": msg})


@bp.route("/api/rescue/sftp/mount", methods=["POST"])
@safe_api
@require_auth
@validate_json(["host", "remote_path", "mount_point"])
def sftp_mount(data):
    ok, mp = _validate_mount_path(data["mount_point"], ALLOWED_MOUNT_PREFIXES)
    if not ok:
        return jsonify({"success": False, "message": mp}), 400
    host = data["host"].strip()
    if not host or len(host) > 256:
        return jsonify({"success": False, "message": "Invalid host"}), 400
    out, code = rescue.mount_sftp(
        host=host,
        remote_path=data["remote_path"].strip(),
        mount_point=mp,
        port=data.get("port", 22),
        user=data.get("user", "root"),
        options=data.get("options", ""),
        key_file=data.get("key_file", ""),
    )
    return jsonify({"success": code == 0, "message": out or "已挂载"})


@bp.route("/api/rescue/sftp/umount", methods=["POST"])
@safe_api
@require_auth
@validate_json(["mount_point"])
def sftp_umount(data):
    ok, mp = _validate_mount_path(data["mount_point"], ALLOWED_MOUNT_PREFIXES)
    if not ok:
        return jsonify({"success": False, "message": mp}), 400
    out, code = rescue.umount_sftp(mp)
    return jsonify({"success": code == 0, "message": out or "已卸载"})


@bp.route("/api/rescue/sftp/mounted")
@safe_api
@require_auth
def sftp_mounted():
    return jsonify({"mounts": rescue.get_sftp_mounts()})


@bp.route("/api/rescue/browse")
@safe_api
@require_auth
def browse_dir():
    path = request.args.get("path", "/").strip() or "/"
    items = rescue.list_directory(path)
    return jsonify({"success": True, "items": items, "path": path})


# ═══════════════════ 系统快照 / 备份 ═══════════════════

@bp.route("/api/rescue/backup/create", methods=["POST"])
@safe_api
@require_auth
@validate_json([])
def backup_create(data):
    """创建系统快照。可选参数: name, include_home。"""
    result = rescue.create_system_snapshot(
        name=data.get("name", ""),
        include_home=data.get("include_home", False),
    )
    return jsonify(result)


@bp.route("/api/rescue/backup/list")
@safe_api
@require_auth
def backup_list():
    """列出所有快照。"""
    return jsonify({"snapshots": rescue.list_snapshots()})


@bp.route("/api/rescue/backup/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def backup_delete(data):
    """删除指定快照。"""
    ok, msg = rescue.delete_snapshot(data["name"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/rescue/backup/restore", methods=["POST"])
@safe_api
@require_auth
@validate_json(["snapshot", "filename"])
def backup_restore(data):
    """从快照恢复单个配置文件。"""
    ok, msg = rescue.restore_config_file(data["snapshot"], data["filename"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/rescue/backup/compare")
@safe_api
@require_auth
def backup_compare():
    """比较快照与当前系统。"""
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "快照名称不能为空"}), 400
    return jsonify(rescue.compare_snapshot(name))
