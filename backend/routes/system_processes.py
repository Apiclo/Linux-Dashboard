"""Process management routes."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth
from core.system import processes

bp = Blueprint("system_processes", __name__)


@bp.route("/api/system/processes")
@safe_api
@require_auth
def list_procs():
    sort = request.args.get("sort", "cpu")
    filter_name = request.args.get("filter", "")
    limit = request.args.get("limit", 100, type=int)
    return jsonify({"processes": processes.list_processes(sort, filter_name, limit)})


@bp.route("/api/system/processes/tree")
@safe_api
@require_auth
def proc_tree():
    return jsonify(processes.get_process_tree())


@bp.route("/api/system/processes/top")
@safe_api
@require_auth
def proc_top():
    limit = request.args.get("limit", 10, type=int)
    return jsonify(processes.get_top_processes(limit))


@bp.route("/api/system/processes/load")
@safe_api
@require_auth
def proc_load():
    return jsonify(processes.get_system_load())


@bp.route("/api/system/processes/<int:pid>")
@safe_api
@require_auth
def proc_detail(pid):
    return jsonify(processes.get_process_detail(pid))


@bp.route("/api/system/processes/kill", methods=["POST"])
@safe_api
@require_auth
@validate_json(["pid"])
def proc_kill(data):
    ok, msg = processes.kill_process(data["pid"], data.get("signal", "SIGTERM"))
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/system/processes/renice", methods=["POST"])
@safe_api
@require_auth
@validate_json(["pid", "nice"])
def proc_renice(data):
    ok, msg = processes.renice_process(data["pid"], data["nice"])
    return jsonify({"success": ok, "message": msg})
