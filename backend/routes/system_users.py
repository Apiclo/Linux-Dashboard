"""System user management routes."""
from flask import Blueprint, jsonify
from utils.helpers import safe_api, validate_json, require_auth
from core import system

bp = Blueprint("system_users", __name__)


@bp.route("/api/system/users")
@safe_api
@require_auth
def users():
    return jsonify({"users": system.get_users()})


@bp.route("/api/system/users/add", methods=["POST"])
@safe_api
@require_auth
@validate_json(["username", "password"])
def user_add(data):
    return jsonify(system.add_user(
        data["username"], data["password"],
        data.get("groups", ""), data.get("shell", "/bin/bash")
    ))


@bp.route("/api/system/users/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["username"])
def user_delete(data):
    return jsonify(system.delete_user(data["username"]))


@bp.route("/api/system/users/password", methods=["POST"])
@safe_api
@require_auth
@validate_json(["username", "password"])
def user_password(data):
    return jsonify(system.change_password(data["username"], data["password"]))
