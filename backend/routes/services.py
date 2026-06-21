"""Service routes."""
from flask import Blueprint, jsonify, request
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
    lines = request.args.get("lines", 80, type=int)
    return jsonify({"logs": services_core.get_service_logs(name, lines)})


@bp.route("/api/service/dependencies/<name>")
@safe_api
@require_auth
def dependencies(name):
    return jsonify(services_core.get_service_dependencies(name))


@bp.route("/api/service/unit-file/<name>")
@safe_api
@require_auth
def unit_file(name):
    return jsonify(services_core.get_unit_file(name))


@bp.route("/api/service/status/<name>")
@safe_api
@require_auth
def status_detail(name):
    return jsonify(services_core.get_service_status_detail(name))


@bp.route("/api/service/enablement")
@safe_api
@require_auth
def enablement():
    return jsonify({"services": services_core.get_service_enablement()})
