"""Timer & cron management routes."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth
from core.system import timers

bp = Blueprint("system_timers", __name__)


@bp.route("/api/system/timers")
@safe_api
@require_auth
def list_timers():
    return jsonify(timers.list_systemd_timers())


@bp.route("/api/system/timers/<name>")
@safe_api
@require_auth
def timer_detail(name):
    return jsonify(timers.get_timer_detail(name))


@bp.route("/api/system/timers/action", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "action"])
def timer_action(data):
    ok, msg = timers.timer_action(data["name"], data["action"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/system/crontab/parsed")
@safe_api
@require_auth
def crontab_parsed():
    return jsonify(timers.parse_crontab())


@bp.route("/api/system/crontab/system")
@safe_api
@require_auth
def crontab_system():
    return jsonify(timers.get_system_crontabs())
