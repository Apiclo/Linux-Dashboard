"""System rescue routes: ISO management + chroot."""
import os
from typing import List, Tuple
from flask import Blueprint, jsonify, request, session
from utils.helpers import safe_api, validate_json, require_auth, run_cmd, safe_quote
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

    result = {"success": True, "message": f"ISO 已挂载到 {mp}"}

    if configure:
        d = distro.detect_distro()
        from core.gpu import _resolve_distro_family
        family = _resolve_distro_family(d)
        ok, msg = rescue.configure_local_repo(mp, family)
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
        from core.gpu import _resolve_distro_family
        family = _resolve_distro_family(d)
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
    from core.gpu import _resolve_distro_family
    family = _resolve_distro_family(d)
    return jsonify(rescue.get_repo_status(family))


@bp.route("/api/rescue/iso/remove-repo", methods=["POST"])
@safe_api
@require_auth
def iso_remove_repo():
    d = distro.detect_distro()
    from core.gpu import _resolve_distro_family
    family = _resolve_distro_family(d)
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
        f"sudo cp {safe_quote(tmp)} {safe_quote(root)}/tmp/_penguinfu_cmd.sh && "
        f"sudo chroot {safe_quote(root)} /bin/bash /tmp/_penguinfu_cmd.sh",
        timeout=30
    )
    run_cmd(f"sudo rm -f {safe_quote(root)}/tmp/_penguinfu_cmd.sh 2>/dev/null", timeout=5)
    return jsonify({"success": code == 0, "output": out, "exit_code": code})
