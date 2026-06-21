"""RAID management routes."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth
from core import raid

bp = Blueprint("raid", __name__)


@bp.route("/api/raid/arrays")
@safe_api
@require_auth
def arrays():
    return jsonify({"arrays": raid.get_raid_arrays()})


@bp.route("/api/raid/devices")
@safe_api
@require_auth
def devices():
    return jsonify({"devices": raid.get_available_devices()})


@bp.route("/api/raid/create", methods=["POST"])
@safe_api
@require_auth
@validate_json(["level", "devices"])
def create(data):
    return jsonify(raid.create_raid(data["level"], data["devices"], data.get("name", "")))


@bp.route("/api/raid/manage", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device", "action"])
def manage(data):
    return jsonify(raid.manage_raid(data["device"], data["action"]))


@bp.route("/api/raid/detail")
@safe_api
@require_auth
def detail():
    device = request.args.get("device", "")
    return jsonify(raid.get_raid_detail(device))
