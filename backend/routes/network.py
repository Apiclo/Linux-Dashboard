"""Network routes."""
import re
from flask import Blueprint, jsonify, request
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
    ok, msg = network.fw_port_action("allow", data["port"], data.get("protocol", "tcp"))
    return jsonify({"success": ok, "message": msg or "已放行"})


@bp.route("/api/network/firewall/deny", methods=["POST"])
@safe_api
@require_auth
@validate_json(["port"])
def fw_deny(data):
    ok, msg = network.fw_port_action("deny", data["port"], data.get("protocol", "tcp"))
    return jsonify({"success": ok, "message": msg or "已禁止"})


@bp.route("/api/network/firewall/rules")
@safe_api
@require_auth
def firewall_rules():
    tool = request.args.get("tool", "").strip()
    return jsonify({"rules": network.get_firewall_rules(tool)})


@bp.route("/api/network/manager")
@safe_api
@require_auth
def network_manager():
    return jsonify({"manager": network.detect_network_manager()})


# ── IP 配置 ──

@bp.route("/api/network/ip-config/<iface>")
@safe_api
@require_auth
def ip_config(iface):
    return jsonify(network.get_ip_config(iface))


@bp.route("/api/network/ip/static", methods=["POST"])
@safe_api
@require_auth
@validate_json(["interface", "address"])
def set_static(data):
    out, code = network.set_static_ip(
        data["interface"], data["address"],
        data.get("netmask", "24"), data.get("gateway", ""), data.get("dns", "")
    )
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/ip/dhcp", methods=["POST"])
@safe_api
@require_auth
@validate_json(["interface"])
def set_dhcp(data):
    out, code = network.set_dhcp(data["interface"])
    return jsonify({"success": code == 0, "message": out})


# ── 网络绑定 ──

@bp.route("/api/network/bonds")
@safe_api
@require_auth
def bonds():
    return jsonify({"bonds": network.get_bonds(), "slaves": network.get_available_slaves(), "modes": network.BOND_MODES})


@bp.route("/api/network/bond/create", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "slaves"])
def bond_create(data):
    out, code = network.create_bond(
        data["name"], data["slaves"], data.get("mode", "1"),
        data.get("ip", ""), data.get("gateway", "")
    )
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/bond/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def bond_delete(data):
    out, code = network.delete_bond(data["name"])
    return jsonify({"success": code == 0, "message": out})


# ── VLAN ──

@bp.route("/api/network/vlans")
@safe_api
@require_auth
def vlans():
    return jsonify({"vlans": network.get_vlans()})


@bp.route("/api/network/vlan/create", methods=["POST"])
@safe_api
@require_auth
@validate_json(["parent", "vlan_id"])
def vlan_create(data):
    out, code = network.create_vlan(data["parent"], int(data["vlan_id"]), data.get("name", ""))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/vlan/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def vlan_delete(data):
    out, code = network.delete_vlan(data["name"])
    return jsonify({"success": code == 0, "message": out})


# ── Bridge ──

@bp.route("/api/network/bridges")
@safe_api
@require_auth
def bridges():
    return jsonify({"bridges": network.get_bridges()})


@bp.route("/api/network/bridge/create", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def bridge_create(data):
    out, code = network.create_bridge(data["name"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/bridge/add-member", methods=["POST"])
@safe_api
@require_auth
@validate_json(["bridge", "interface"])
def bridge_add(data):
    out, code = network.bridge_add_member(data["bridge"], data["interface"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/bridge/remove-member", methods=["POST"])
@safe_api
@require_auth
@validate_json(["interface"])
def bridge_remove(data):
    out, code = network.bridge_remove_member(data["interface"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/bridge/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def bridge_delete(data):
    out, code = network.delete_bridge(data["name"])
    return jsonify({"success": code == 0, "message": out})


# ── Bond 高级 ──

@bp.route("/api/network/bond/options")
@safe_api
@require_auth
def bond_options():
    return jsonify({"options": network.get_bond_options()})


@bp.route("/api/network/bond/create-advanced", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "slaves"])
def bond_create_advanced(data):
    out, code = network.create_bond_advanced(
        data["name"], data["slaves"], data.get("mode", "1"), data.get("options")
    )
    return jsonify({"success": code == 0, "message": out})


# ── Routes ──

@bp.route("/api/network/routes")
@safe_api
@require_auth
def routes():
    return jsonify({"routes": network.get_routes()})


@bp.route("/api/network/route/add", methods=["POST"])
@safe_api
@require_auth
@validate_json(["dst"])
def route_add(data):
    out, code = network.add_route(
        data["dst"], data.get("gateway", ""), data.get("dev", ""), data.get("metric", "")
    )
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/route/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["dst"])
def route_delete(data):
    out, code = network.delete_route(data["dst"], data.get("gateway", ""))
    return jsonify({"success": code == 0, "message": out})


# ── WireGuard ──

@bp.route("/api/network/wireguard/check")
@safe_api
@require_auth
def wg_check():
    ok, msg = network.wireguard_check()
    return jsonify({"available": ok, "message": msg})


@bp.route("/api/network/wireguard/list")
@safe_api
@require_auth
def wg_list():
    return jsonify({"interfaces": network.get_wireguard_interfaces()})


@bp.route("/api/network/wireguard/create", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def wg_create(data):
    out, code = network.create_wireguard(data["name"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/wireguard/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def wg_delete(data):
    out, code = network.delete_wireguard(data["name"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/network/traffic")
@safe_api
@require_auth
def traffic():
    return jsonify(network.get_network_traffic())


@bp.route("/api/network/firewall/zones")
@safe_api
@require_auth
def fw_zones():
    return jsonify(network.firewalld_get_zones())


@bp.route("/api/network/firewall/rich-rules")
@safe_api
@require_auth
def fw_rich_rules():
    zone = request.args.get("zone", "").strip()
    return jsonify({"rules": network.firewalld_list_rich_rules(zone)})


# ═══════════════ 网络诊断 ═══════════════

@bp.route("/api/network/diag/ping")
@safe_api
@require_auth
def diag_ping():
    host = request.args.get("host", "").strip()
    if not host:
        return jsonify({"success": False, "error": "host required"}), 400
    return jsonify(network.ping_host(
        host,
        count=request.args.get("count", 4, type=int),
        timeout=request.args.get("timeout", 5, type=int),
    ))


@bp.route("/api/network/diag/traceroute")
@safe_api
@require_auth
def diag_traceroute():
    host = request.args.get("host", "").strip()
    if not host:
        return jsonify({"success": False, "error": "host required"}), 400
    return jsonify(network.traceroute_host(
        host,
        max_hops=request.args.get("max_hops", 30, type=int),
    ))


@bp.route("/api/network/diag/dns")
@safe_api
@require_auth
def diag_dns():
    domain = request.args.get("domain", "").strip()
    rtype = request.args.get("type", "A").strip().upper()
    if not domain:
        return jsonify({"success": False, "error": "domain required"}), 400
    return jsonify(network.dns_lookup(domain, rtype))


@bp.route("/api/network/diag/portscan")
@safe_api
@require_auth
def diag_portscan():
    host = request.args.get("host", "").strip()
    if not host:
        return jsonify({"success": False, "error": "host required"}), 400
    ports = request.args.get("ports", "22,80,443,3306,5432,6379,8080,8443")
    return jsonify(network.port_scan(host, ports))


@bp.route("/api/network/diag/connectivity")
@safe_api
@require_auth
def diag_connectivity():
    target = request.args.get("target", "8.8.8.8").strip()
    return jsonify(network.check_connectivity(target))
