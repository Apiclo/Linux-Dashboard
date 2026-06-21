"""Offline package routes."""
import os
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from utils.helpers import safe_api, validate_json, require_auth
from utils.tasks import start_task
from core import gpu

bp = Blueprint("offline", __name__)

OFFLINE_ALLOWED_PREFIXES = ["/tmp/linux-toolbox-uploads", "/tmp/offline-packages", "/opt/offline-packages"]


@bp.route("/api/offline/nvidia-packages")
@safe_api
@require_auth
def nvidia_packages():
    return jsonify(gpu.list_available_nvidia_packages())


@bp.route("/api/offline/generate", methods=["POST"])
@safe_api
@require_auth
@validate_json(["packages"])
def generate(data):
    if not data["packages"]: return jsonify({"success": False, "message": "未选择包"}), 400
    cmd, err = gpu.generate_offline_package(data)
    if err: return jsonify({"success": False, "message": err}), 400
    return jsonify({"task_id": start_task(cmd, "offline_gen")})


@bp.route("/api/offline/generated-list")
@safe_api
@require_auth
def generated_list():
    return jsonify(gpu.list_generated_packages())


@bp.route("/api/gpu/offline/list")
@safe_api
@require_auth
def offline_list():
    return jsonify(gpu.list_offline_packages())


@bp.route("/api/gpu/offline/install", methods=["POST"])
@safe_api
@require_auth
@validate_json(["extract_dir"])
def offline_install(data):
    from utils.helpers import validate_path
    ok, real = validate_path(data["extract_dir"], OFFLINE_ALLOWED_PREFIXES)
    if not ok:
        return jsonify({"success": False, "message": f"Path not allowed: {data['extract_dir']}"}), 403
    cmd, err = gpu.install_offline_package(real, data)
    if err: return jsonify({"success": False, "message": err}), 400
    return jsonify({"task_id": start_task(cmd, "offline")})


@bp.route("/api/gpu/offline/inspect", methods=["POST"])
@safe_api
@require_auth
@validate_json(["extract_dir"])
def offline_inspect(data):
    import json
    from utils.helpers import validate_path
    ok, real = validate_path(data["extract_dir"], OFFLINE_ALLOWED_PREFIXES)
    if not ok:
        return jsonify({"success": False, "message": f"Path not allowed: {data['extract_dir']}"}), 403
    drv = os.path.join(real, "drv_list.json")
    if os.path.exists(drv):
        try:
            with open(drv) as f: return jsonify({"success": True, "meta": json.load(f)})
        except Exception as e: return jsonify({"success": False, "message": str(e)})
    return jsonify({"success": False, "message": "drv_list.json 不存在"})


@bp.route("/api/gpu/offline/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def offline_delete(data):
    ok, msg = gpu.delete_offline_package(data["path"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/upload/runfile", methods=["POST"])
@safe_api
@require_auth
def upload_runfile():
    import shutil
    if "file" not in request.files: return jsonify({"success": False, "message": "未上传文件"}), 400
    f = request.files["file"]
    if not f.filename or not f.filename.endswith(".run"): return jsonify({"success": False, "message": "仅支持 .run"}), 400
    save_dir = "/tmp/linux-toolbox-uploads/runfiles"
    os.makedirs(save_dir, exist_ok=True)
    if shutil.disk_usage(save_dir).free < 500 * 1024 * 1024: return jsonify({"success": False, "message": "磁盘空间不足"}), 507
    safe_name = secure_filename(f.filename) or "uploaded.run"
    save_path = os.path.join(save_dir, safe_name)
    f.save(save_path)
    size = os.path.getsize(save_path)
    info, _ = gpu.get_runfile_info(save_path)
    return jsonify({"success": True, "path": save_path, "filename": safe_name, "size": size, "info": info})


@bp.route("/api/upload/offline", methods=["POST"])
@safe_api
@require_auth
def upload_offline():
    import shutil
    if "file" not in request.files: return jsonify({"success": False, "message": "未上传文件"}), 400
    f = request.files["file"]
    if not f.filename or not (f.filename.endswith(".tar.gz") or f.filename.endswith(".tgz")): return jsonify({"success": False, "message": "仅支持 .tar.gz"}), 400
    if shutil.disk_usage("/tmp").free < 1024 * 1024 * 1024: return jsonify({"success": False, "message": "磁盘空间不足"}), 507
    safe_name = secure_filename(f.filename) or "offline.tar.gz"
    tmp = os.path.join("/tmp/linux-toolbox-uploads", safe_name)
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    f.save(tmp)
    result, err = gpu.parse_offline_package(tmp)
    try: os.remove(tmp)
    except Exception: pass
    if err: return jsonify({"success": False, "message": err}), 400
    return jsonify({"success": True, "meta": result["meta"], "packages": result["packages"], "install_script": result["install_script"], "extract_dir": result["extract_dir"], "package_count": len(result["packages"])})
