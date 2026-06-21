"""Package routes."""
from flask import Blueprint, jsonify
from utils.helpers import safe_api, validate_json, require_auth, validate_package_name
from utils.tasks import start_task
from core import package

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
