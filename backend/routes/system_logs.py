"""System logs, NTP, ulimits, kernel modules, cron routes."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth
from core import system

bp = Blueprint("system_logs", __name__)


@bp.route("/api/system/logs")
@safe_api
@require_auth
def journal_logs():
    try:
        lines = int(request.args.get("lines", "100"))
        lines = max(10, min(lines, 1000))
    except (ValueError, TypeError):
        lines = 100
    unit = request.args.get("unit", "")
    priority = request.args.get("priority", "")
    return jsonify({"logs": system.get_journal_logs(lines, unit, priority)})


@bp.route("/api/system/dmesg")
@safe_api
@require_auth
def dmesg_logs():
    lines = int(request.args.get("lines", "100"))
    level = request.args.get("level", "")
    return jsonify({"logs": system.get_dmesg(lines, level)})


@bp.route("/api/system/audit")
@safe_api
@require_auth
def audit_logs():
    lines = int(request.args.get("lines", "100"))
    return jsonify({"logs": system.get_audit_logs(lines)})


@bp.route("/api/system/crontab")
@safe_api
@require_auth
def crontab_get():
    user = request.args.get("user", "").strip()
    content, u = system.get_crontab(user)
    return jsonify({"content": content, "user": u})


@bp.route("/api/system/crontab", methods=["POST"])
@safe_api
@require_auth
@validate_json(["content"])
def crontab_set(data):
    user = data.get("user", "").strip()
    out, code = system.set_crontab(data["content"], user)
    return jsonify({"success": code == 0, "message": out or "已保存"})


@bp.route("/api/system/ntp")
@safe_api
@require_auth
def ntp_status():
    return jsonify(system.get_ntp_status())


@bp.route("/api/system/ntp", methods=["POST"])
@safe_api
@require_auth
@validate_json(["enable"])
def ntp_toggle(data):
    return jsonify(system.toggle_ntp(data["enable"]))


@bp.route("/api/system/ulimits")
@safe_api
@require_auth
def ulimits():
    return jsonify(system.get_ulimits())


@bp.route("/api/system/ulimits", methods=["POST"])
@safe_api
@require_auth
@validate_json(["content"])
def save_ulimits(data):
    return jsonify(system.save_ulimits(data["content"]))


@bp.route("/api/system/modules")
@safe_api
@require_auth
def modules():
    return jsonify({"modules": system.get_kernel_modules()})


@bp.route("/api/system/modules/manage", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "action"])
def manage_module(data):
    return jsonify(system.manage_kernel_module(data["name"], data["action"]))
