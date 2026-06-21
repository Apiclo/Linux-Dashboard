"""System boot & kernel tuning routes."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth
from core import system

bp = Blueprint("system_boot", __name__)


# ── Boot & Kernel Tuning ──

@bp.route("/api/system/grub-config")
@safe_api
@require_auth
def grub_config():
    """获取引导配置。可选参数 ?bootloader=grub|systemd-boot|refind。"""
    bl = request.args.get("bootloader", "").strip()
    return jsonify(system.get_grub_config(bl))


@bp.route("/api/system/bootloaders")
@safe_api
@require_auth
def bootloaders_list():
    """列出所有已检测到的引导加载器。"""
    from core.system.boot import _detect_all_bootloaders
    return jsonify({"bootloaders": _detect_all_bootloaders()})


@bp.route("/api/system/grub-default", methods=["POST"])
@safe_api
@require_auth
@validate_json(["value"])
def grub_default(data):
    """设置默认启动内核。"""
    out, code = system.set_grub_default(data["value"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/system/grub-cmdline", methods=["POST"])
@safe_api
@require_auth
@validate_json(["params"])
def grub_cmdline(data):
    """设置 GRUB 内核引导参数。"""
    out, code = system.set_grub_cmdline(data["params"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/system/grub-cmdline-presets")
@safe_api
@require_auth
def grub_cmdline_presets():
    """获取引导参数预设列表。"""
    return jsonify({"presets": system.BOOT_PARAM_PRESETS})


@bp.route("/api/system/cpu-governor")
@safe_api
@require_auth
def cpu_governor():
    return jsonify(system.get_cpu_governor())


@bp.route("/api/system/cpu-governor", methods=["POST"])
@safe_api
@require_auth
@validate_json(["governor"])
def cpu_governor_set(data):
    ok, msg = system.set_cpu_governor(data["governor"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/system/io-scheduler")
@safe_api
@require_auth
def io_scheduler():
    return jsonify(system.get_io_scheduler())


@bp.route("/api/system/io-scheduler", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device", "scheduler"])
def io_scheduler_set(data):
    ok, msg = system.set_io_scheduler(data["device"], data["scheduler"])
    return jsonify({"success": ok, "message": msg})


# ── Grub repair ──

@bp.route("/api/system/grub-repair", methods=["POST"])
@safe_api
@require_auth
def grub_repair():
    data = request.get_json(silent=True) or {}
    out, code = system.repair_grub(data.get("disk", ""), data.get("root", ""))
    return jsonify({"success": code == 0, "message": out})


# ── initramfs rebuild ──

@bp.route("/api/system/initramfs-rebuild", methods=["POST"])
@safe_api
@require_auth
def initramfs_rebuild():
    from utils.tasks import start_task
    data = request.get_json(silent=True) or {}
    cmd = system.rebuild_initramfs(data.get("all", True))
    return jsonify({"task_id": start_task(cmd, "initramfs")})
