"""Service routes."""
from flask import Blueprint, jsonify
from utils.helpers import safe_api, validate_json, require_auth
from core import services as services_core

bp = Blueprint("services", __name__)


@bp.route("/api/services")
@safe_api
@require_auth
def services():
    return jsonify(services_core.get_services())


@bp.route("/api/service/action", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "action"])
def action(data):
    out, code = services_core.service_action(data["name"], data["action"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/service/logs/<name>")
@safe_api
@require_auth
def logs(name):
    from flask import request
    lines = request.args.get("lines", 80, type=int)
    return jsonify({"logs": services_core.get_service_logs(name, lines)})
