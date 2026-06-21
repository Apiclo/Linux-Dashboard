"""Disk routes."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth
from core import disk

bp = Blueprint("disk", __name__)


@bp.route("/api/disk/devices")
@safe_api
@require_auth
def devices():
    return jsonify(disk.get_block_devices())


@bp.route("/api/disk/usage")
@safe_api
@require_auth
def usage():
    return jsonify({"usage": disk.get_disk_usage()})


@bp.route("/api/disk/fstab")
@safe_api
@require_auth
def fstab():
    return jsonify({"content": disk.get_fstab()})


@bp.route("/api/disk/fstab/save", methods=["POST"])
@safe_api
@require_auth
@validate_json(["content"])
def fstab_save(data):
    return jsonify({"success": disk.save_fstab(data["content"])})


@bp.route("/api/disk/mount", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device", "mountpoint"])
def mount(data):
    out, code = disk.mount_device(data["device"], data["mountpoint"], data.get("fstype", "auto"))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/disk/umount", methods=["POST"])
@safe_api
@require_auth
@validate_json(["target"])
def umount(data):
    ok, msg = disk.umount_device(data["target"])
    return jsonify({"success": ok, "message": msg})
