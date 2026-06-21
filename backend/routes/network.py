"""Network routes."""
import re
from flask import Blueprint, jsonify
from utils.helpers import safe_api, validate_json, require_auth, validate_fw_command, run_cmd, safe_quote
from core import network

bp = Blueprint("network", __name__)


@bp.route("/api/network/interfaces")
@safe_api
@require_auth
def interfaces():
    return jsonify(network.get_network_interfaces())


@bp.route("/api/network/dns")
@safe_api
@require_auth
def dns():
    return jsonify({"dns": network.get_dns()})


@bp.route("/api/network/firewall")
@safe_api
@require_auth
def firewall():
    return jsonify(network.get_firewall_status())


@bp.route("/api/network/fwcmd", methods=["POST"])
@safe_api
@require_auth
@validate_json(["cmd"])
def fwcmd(data):
    ok, validated = validate_fw_command(data["cmd"])
    if not ok:
        return jsonify({"success": False, "message": validated}), 403
    out, code = run_cmd(f"sudo {validated}", timeout=15)
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/dns", methods=["POST"])
@safe_api
@require_auth
@validate_json(["servers"])
def set_dns(data):
    return jsonify(network.set_dns(data["servers"]))


@bp.route("/api/network/ports")
@safe_api
@require_auth
def ports():
    return jsonify({"ports": network.get_listen_ports()})


# ── Semantic endpoints (replacing frontend shell-command construction) ──

@bp.route("/api/network/interface/action", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "action"])
def interface_action(data):
    """Bring an interface up, down, or restart it."""
    name = data["name"].strip()
    action = data["action"].strip().lower()
    if not re.match(r'^[a-zA-Z0-9._\-:]+$', name):
        return jsonify({"success": False, "message": "Invalid interface name"}), 400
    if action not in ("up", "down", "restart"):
        return jsonify({"success": False, "message": "Action must be up, down, or restart"}), 400
    if action == "restart":
        out, code = run_cmd(f"sudo ip link set {safe_quote(name)} down && sudo ip link set {safe_quote(name)} up", timeout=15)
    else:
        out, code = run_cmd(f"sudo ip link set {safe_quote(name)} {action}", timeout=10)
    return jsonify({"success": code == 0, "message": out or f"Interface {name} {action}"})


@bp.route("/api/network/firewall/allow", methods=["POST"])
@safe_api
@require_auth
@validate_json(["port"])
def fw_allow(data):
    """Allow a port through the firewall."""
    port = str(data["port"]).strip()
    protocol = data.get("protocol", "tcp").strip().lower()
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        return jsonify({"success": False, "message": "Invalid port number (1-65535)"}), 400
    if protocol not in ("tcp", "udp"):
        return jsonify({"success": False, "message": "Protocol must be tcp or udp"}), 400
    out, code = run_cmd(f"sudo ufw allow {port}/{protocol}", timeout=15)
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/firewall/deny", methods=["POST"])
@safe_api
@require_auth
@validate_json(["port"])
def fw_deny(data):
    """Deny a port through the firewall."""
    port = str(data["port"]).strip()
    protocol = data.get("protocol", "tcp").strip().lower()
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        return jsonify({"success": False, "message": "Invalid port number (1-65535)"}), 400
    if protocol not in ("tcp", "udp"):
        return jsonify({"success": False, "message": "Protocol must be tcp or udp"}), 400
    out, code = run_cmd(f"sudo ufw deny {port}/{protocol}", timeout=15)
    return jsonify({"success": code == 0, "message": out})
