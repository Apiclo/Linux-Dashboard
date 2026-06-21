"""GPU routes."""
import logging
from flask import Blueprint, jsonify, request, session
from utils.helpers import safe_api, validate_json, require_auth
from utils.tasks import start_task
from core import gpu

log = logging.getLogger("audit")

bp = Blueprint("gpu", __name__)


@bp.route("/api/gpu/detect")
@safe_api
@require_auth
def detect():
    return jsonify(gpu.get_detect_data())


@bp.route("/api/gpu/compatibility")
@safe_api
@require_auth
def compatibility():
    return jsonify(gpu.check_compatibility())


@bp.route("/api/gpu/nvidia/versions")
@safe_api
@require_auth
def nvidia_versions():
    return jsonify(gpu.get_nvidia_repo_versions())


@bp.route("/api/gpu/cuda/versions")
@safe_api
@require_auth
def cuda_versions():
    return jsonify(gpu.fetch_cuda_versions())


@bp.route("/api/gpu/nouveau/blacklist", methods=["POST"])
@safe_api
@require_auth
def blacklist():
    ok, msg = gpu.blacklist_nouveau()
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/gpu/distro")
@safe_api
@require_auth
def distro():
    return jsonify(gpu.get_distro_info())


@bp.route("/api/gpu/runfile/validate", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def runfile_validate(data):
    ok, msg = gpu.validate_runfile(data["path"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/gpu/install/repo", methods=["POST"])
@safe_api
@require_auth
@validate_json(["package"])
def install_repo(data):
    return jsonify({"task_id": start_task(gpu.install_nvidia_repo(data), "gpu_repo")})


@bp.route("/api/gpu/install/runfile", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def install_runfile(data):
    cmd, err = gpu.install_nvidia_runfile(data)
    if err: return jsonify({"success": False, "message": err})
    return jsonify({"task_id": start_task(cmd, "gpu_run")})


@bp.route("/api/gpu/install/amd", methods=["POST"])
@safe_api
@require_auth
def install_amd():
    return jsonify({"task_id": start_task(gpu.install_amd_driver(), "gpu_amd")})


@bp.route("/api/gpu/install/intel", methods=["POST"])
@safe_api
@require_auth
def install_intel():
    return jsonify({"task_id": start_task(gpu.install_intel_driver(), "gpu_intel")})


@bp.route("/api/gpu/install/rocm", methods=["POST"])
@safe_api
@require_auth
def install_rocm():
    usecase = request.get_json(silent=True) or {}
    return jsonify({"task_id": start_task(
        gpu.install_rocm_driver(usecase.get("usecase", "rocm")), "gpu_rocm"
    )})


@bp.route("/api/gpu/install/custom", methods=["POST"])
@safe_api
@require_auth
@validate_json(["cmd"])
def install_custom(data):
    cmd = data["cmd"].strip()
    if not cmd:
        return jsonify({"success": False, "message": "Empty command"}), 400
    if len(cmd) > 2000:
        return jsonify({"success": False, "message": "Command too long"}), 400
    # Audit log with user info
    user = session.get("username", "unknown")
    log.warning(f"CUSTOM_CMD by {user}: {cmd[:200]}")
    return jsonify({"task_id": start_task(cmd, "gpu_custom")})


@bp.route("/api/gpu/uninstall", methods=["POST"])
@safe_api
@require_auth
def uninstall():
    return jsonify({"task_id": start_task(gpu.uninstall_nvidia(), "gpu_uninstall")})


@bp.route("/api/gpu/cuda/setup-repo", methods=["POST"])
@safe_api
@require_auth
def cuda_setup_repo():
    """仅设置 CUDA 仓库源，不安装包。"""
    return jsonify({"task_id": start_task(gpu.setup_cuda_repo(), "cuda_setup")})


@bp.route("/api/gpu/nvidia-smi/realtime")
@safe_api
@require_auth
def nvidia_smi_realtime():
    """获取 nvidia-smi 实时数据。"""
    return jsonify({"data": gpu.get_nvidia_smi_realtime()})


@bp.route("/api/gpu/nvidia-smi/monitor", methods=["POST"])
@safe_api
@require_auth
def nvidia_monitor():
    """启动 nvidia-smi 实时监控 SSE 流。"""
    return jsonify({"task_id": start_task(gpu.start_nvidia_monitor(), "nvidia_monitor")})


@bp.route("/api/gpu/cuda/install", methods=["POST"])
@safe_api
@require_auth
def cuda_install():
    data = request.get_json(silent=True) or {}
    return jsonify({"task_id": start_task(gpu.install_cuda_toolkit(data.get("method", "network"), data.get("version", "")), "cuda")})
