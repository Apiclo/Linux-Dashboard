"""Package routes."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth, validate_package_name
from utils.tasks import start_task
from core import package
from core import package_cleanup

bp = Blueprint("packages", __name__)


@bp.route("/api/packages/software")
@safe_api
@require_auth
def software():
    return jsonify(package.COMMON_SOFTWARE)


@bp.route("/api/packages/search")
@safe_api
@require_auth
def search():
    from flask import request
    q = request.args.get("q", "").strip()
    return jsonify({"result": package.search_package(q) if q else ""})


@bp.route("/api/packages/search-structured")
@safe_api
@require_auth
def search_structured():
    q = request.args.get("q", "").strip()
    return jsonify({"results": package.search_package_structured(q) if q else []})


@bp.route("/api/packages/install", methods=["POST"])
@safe_api
@require_auth
@validate_json(["package"])
def install(data):
    pkg = data["package"].strip()
    ok, err = validate_package_name(pkg)
    if not ok:
        return jsonify({"success": False, "message": err}), 400
    cmd, err2 = package.get_install_command(pkg)
    if not cmd:
        return jsonify({"success": False, "message": err2}), 400
    return jsonify({"task_id": start_task(cmd, "pkg")})


@bp.route("/api/packages/remove", methods=["POST"])
@safe_api
@require_auth
@validate_json(["package"])
def remove(data):
    pkg = data["package"].strip()
    ok, err = validate_package_name(pkg)
    if not ok:
        return jsonify({"success": False, "message": err}), 400
    cmd, err2 = package.get_remove_command(pkg)
    if not cmd:
        return jsonify({"success": False, "message": err2}), 400
    return jsonify({"task_id": start_task(cmd, "pkg_rm")})


# ── 已安装包列表 ──

@bp.route("/api/packages/installed")
@safe_api
@require_auth
def installed():
    q = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", "500")), 2000)
    return jsonify({"packages": package.get_installed_packages(q, limit)})


# ── 软件源管理 ──

@bp.route("/api/packages/repos")
@safe_api
@require_auth
def repos():
    return jsonify(package.get_repos())


@bp.route("/api/packages/repo/add", methods=["POST"])
@safe_api
@require_auth
@validate_json(["url"])
def repo_add(data):
    ok, msg = package.add_repo(data["url"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/packages/repo/remove", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def repo_remove(data):
    ok, msg = package.remove_repo_file(data["path"])
    return jsonify({"success": ok, "message": msg})


# ── 批量操作 ──

@bp.route("/api/packages/batch/install", methods=["POST"])
@safe_api
@require_auth
@validate_json(["packages"])
def batch_install(data):
    cmd = package.batch_install(data["packages"])
    return jsonify({"task_id": start_task(cmd, "pkg_batch_install")})


@bp.route("/api/packages/batch/remove", methods=["POST"])
@safe_api
@require_auth
@validate_json(["packages"])
def batch_remove(data):
    cmd = package.batch_remove(data["packages"])
    return jsonify({"task_id": start_task(cmd, "pkg_batch_remove")})


# ── 更新历史 ──

@bp.route("/api/packages/update-history")
@safe_api
@require_auth
def update_history():
    return jsonify({"history": package.get_update_history()})


@bp.route("/api/packages/batch/update", methods=["POST"])
@safe_api
@require_auth
def batch_update():
    cmd = package.batch_update()
    package.log_update_action("update", "all", "started")
    return jsonify({"task_id": start_task(cmd, "pkg_batch_update")})


# ── 软件源原始文件编辑 ──

@bp.route("/api/packages/repo-raw")
@safe_api
@require_auth
def repo_raw_get():
    return jsonify(package.get_repo_raw())


@bp.route("/api/packages/repo-raw", methods=["POST"])
@safe_api
@require_auth
@validate_json(["file", "content"])
def repo_raw_save(data):
    ok, msg = package.save_repo_raw(data["file"], data["content"])
    return jsonify({"success": ok, "message": msg})


# ── 包清理与文件列表 ──

@bp.route("/api/packages/orphans")
@safe_api
@require_auth
def orphans():
    return jsonify(package_cleanup.find_orphaned_packages())


@bp.route("/api/packages/cleanup-cache", methods=["POST"])
@safe_api
@require_auth
def cleanup_cache():
    return jsonify(package_cleanup.clean_package_cache())


@bp.route("/api/packages/files/<pkg>")
@safe_api
@require_auth
def package_files(pkg):
    return jsonify(package_cleanup.get_package_files(pkg))


# add missing request import
from flask import request
