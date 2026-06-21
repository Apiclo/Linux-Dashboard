"""Config routes."""
import os
from flask import Blueprint, jsonify
from utils.helpers import safe_api, validate_json, require_auth, validate_path, run_cmd, atomic_sudo_write, safe_quote
from core.config_presets import PRESETS

bp = Blueprint("config", __name__)


@bp.route("/api/config/presets")
@safe_api
@require_auth
def presets():
    return jsonify(PRESETS)


@bp.route("/api/config/read", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def read_config(data):
    path = os.path.expanduser(data["path"])
    ok, real = validate_path(path)
    if not ok: return jsonify({"success": False, "message": "Access denied"}), 403
    try:
        with open(real) as f:
            content = f.read()
        # Pre-parse values for the preset's keys so the frontend doesn't need to
        parsed = {}
        preset_name = data.get("preset", "")
        if preset_name and preset_name in PRESETS:
            for pk in PRESETS[preset_name]["keys"]:
                for line in content.splitlines():
                    s = line.strip()
                    if not s or s.startswith('#'):
                        continue
                    k = pk["key"]
                    if s.startswith(k + '='):
                        parsed[k] = s.split('=', 1)[1].strip().strip('"\'')
                        break
                    if s.startswith(k + ' '):
                        parsed[k] = s.split(None, 1)[1].strip().strip('"\'')
                        break
        return jsonify({"success": True, "content": content, "path": real, "parsed": parsed})
    except Exception as e: return jsonify({"success": False, "message": str(e)})


@bp.route("/api/config/save", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path", "content"])
def save_config(data):
    path = os.path.expanduser(data["path"])
    ok, real = validate_path(path)
    if not ok: return jsonify({"success": False, "message": "Access denied"}), 403
    try:
        ok, msg = atomic_sudo_write(real, data["content"])
        return jsonify({"success": ok, "path": real})
    except Exception as e: return jsonify({"success": False, "message": str(e)})


@bp.route("/api/config/setparam", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path", "key", "value"])
def setparam(data):
    path = os.path.expanduser(data["path"])
    ok, real = validate_path(path)
    if not ok: return jsonify({"success": False, "message": "Access denied"}), 403
    key, value = data["key"], data["value"]
    # 防御 newline 注入
    if '\n' in key or '\r' in key or '\n' in value or '\r' in value:
        return jsonify({"success": False, "message": "Newlines not allowed in key or value"}), 400
    try:
        content = ""
        if os.path.exists(real):
            with open(real) as f: content = f.read()
        lines = content.splitlines()
        found = False
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith(key + "="): lines[i] = f"{key}={value}"; found = True; break
            if s.startswith(key + " "): lines[i] = f"{key} {value}"; found = True; break
        if not found: lines.append(f"{key}={value}")
        new = "\n".join(lines) + "\n"
        ok, msg = atomic_sudo_write(real, new)
        return jsonify({"success": ok, "content": new})
    except Exception as e: return jsonify({"success": False, "message": str(e)})
