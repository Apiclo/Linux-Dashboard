"""Firewall status, rules, and port allow/deny operations."""
import os
from typing import Dict, Tuple, List
from utils.helpers import run_cmd, safe_quote

NFT_TABLE = "tuxtacklebox"


def _detect_firewall_tools():
    """Return dict of installed firewall tools."""
    tools = {}
    for tool in ('ufw', 'firewall-cmd', 'nft', 'iptables'):
        _, code = run_cmd(f'which {tool} 2>/dev/null')
        tools[tool] = (code == 0)
    return tools


# ---------------------------------------------------------------------------
#  nftables – named-table helper functions (idempotent)
# ---------------------------------------------------------------------------

def _nft_table_exists(table: str = NFT_TABLE) -> bool:
    """Check whether the named nftables table exists."""
    out, code = run_cmd(f"sudo nft list table inet {safe_quote(table)} 2>/dev/null")
    return code == 0 and out.strip() != ""


def _nft_ensure_table(table: str = NFT_TABLE) -> None:
    """Create the named inet table and its base input chain if missing."""
    if not _nft_table_exists(table):
        run_cmd(f"sudo nft add table inet {safe_quote(table)} 2>/dev/null", timeout=10)
    # Ensure a base input chain exists for the table
    out, _ = run_cmd(f"sudo nft list chain inet {safe_quote(table)} input 2>/dev/null")
    if "Error" in out or "not found" in out.lower():
        run_cmd(f"sudo nft add chain inet {safe_quote(table)} input '{{ type filter hook input priority 0; }}' 2>/dev/null", timeout=10)


def _nft_rule_exists(rule: str, table: str = NFT_TABLE) -> bool:
    """Check whether a rule already exists in the table."""
    out, _ = run_cmd(f"sudo nft list table inet {safe_quote(table)} 2>/dev/null")
    return rule in out


def nftables_add_rule(rule: str, family: str = "inet", table: str = NFT_TABLE,
                       chain: str = "input") -> Tuple[bool, str]:
    """Add an nftables rule to the named table/chain (idempotent).

    Args:
        rule:   The rule body, e.g. "tcp dport 22 accept".
        family: nft family – "inet", "ip", or "ip6".
        table:  Table name (default: tuxtacklebox).
        chain:  Chain name (default: input).

    Returns:
        (success, message) tuple.
    """
    _nft_ensure_table(table)

    # Idempotency: check if the exact rule string already appears
    if _nft_rule_exists(rule, table):
        return True, f"Rule already exists: {rule}"

    out, code = run_cmd(
        f"sudo nft add rule {safe_quote(family)} {safe_quote(table)} {safe_quote(chain)} {rule} 2>&1",
        timeout=10
    )
    return code == 0, out.strip()


def nftables_delete_rule(rule: str, family: str = "inet", table: str = NFT_TABLE,
                          chain: str = "input") -> Tuple[bool, str]:
    """Delete an nftables rule from the named table/chain (idempotent).

    Args:
        rule:   The rule body, e.g. "tcp dport 22 accept".
        family: nft family.
        table:  Table name.
        chain:  Chain name.

    Returns:
        (success, message) tuple.
    """
    if not _nft_table_exists(table):
        return True, "Table does not exist – nothing to delete"

    # Idempotency: if the rule is not present, nothing to do
    if not _nft_rule_exists(rule, table):
        return True, f"Rule not found (already absent): {rule}"

    out, code = run_cmd(
        f"sudo nft delete rule {safe_quote(family)} {safe_quote(table)} "
        f"{safe_quote(chain)} handle $(sudo nft -a list table inet {safe_quote(table)} 2>/dev/null | "
        f"grep -F '{rule}' | grep -oP 'handle \\K\\d+' | tail -1) 2>&1",
        timeout=10
    )
    return code == 0, out.strip()


def get_firewall_status() -> Dict:
    """深度检测所有防火墙状态（ufw / firewalld / nftables / iptables）。"""
    result = {
        "active": None,          # 当前激活的防火墙
        "installed": [],         # 已安装的防火墙列表
        "ufw": {"installed": False, "active": False, "status": "", "default_policy": ""},
        "firewalld": {"installed": False, "active": False, "status": "", "zones": []},
        "nftables": {"installed": False, "active": False, "rules_count": 0},
        "iptables": {"installed": False, "active": False, "rules_count": 0},
    }

    tools = _detect_firewall_tools()

    # UFW
    if tools['ufw']:
        result["ufw"]["installed"] = True
        result["installed"].append("ufw")
        out, _ = run_cmd("sudo ufw status 2>/dev/null")
        result["ufw"]["status"] = out.strip()
        if "active" in out.lower():
            result["ufw"]["active"] = True
            result["active"] = "ufw"
        default_out, _ = run_cmd("sudo ufw status verbose 2>/dev/null | grep 'Default:'")
        if default_out:
            result["ufw"]["default_policy"] = default_out.strip()

    # Firewalld
    if tools['firewall-cmd']:
        result["firewalld"]["installed"] = True
        result["installed"].append("firewalld")
        state_out, sc = run_cmd("sudo firewall-cmd --state 2>/dev/null")
        result["firewalld"]["status"] = state_out.strip()
        if sc == 0 and "running" in state_out:
            result["firewalld"]["active"] = True
            result["active"] = "firewalld"
        zones_out, _ = run_cmd("sudo firewall-cmd --get-active-zones 2>/dev/null")
        for line in zones_out.splitlines():
            line = line.strip()
            if line and not line.startswith("interfaces:"):
                result["firewalld"]["zones"].append(line)

    # nftables
    if tools['nft']:
        result["nftables"]["installed"] = True
        result["installed"].append("nftables")
        rules_out, _ = run_cmd("sudo nft list ruleset 2>/dev/null")
        if rules_out.strip():
            result["nftables"]["active"] = True
            result["nftables"]["rules_count"] = rules_out.count("add rule")
            if not result["active"]:
                result["active"] = "nftables"

    # iptables (legacy)
    if tools['iptables']:
        result["iptables"]["installed"] = True
        result["installed"].append("iptables")
        rules_out, _ = run_cmd("sudo iptables -L -n 2>/dev/null | grep -v '^Chain' | grep -v '^target' | grep -v '^$' | wc -l")
        try:
            result["iptables"]["rules_count"] = int(rules_out.strip())
        except ValueError:
            pass
        if result["iptables"]["rules_count"] > 0:
            result["iptables"]["active"] = True
            if not result["active"]:
                result["active"] = "iptables"

    # Safety: active must always be one of the known firewall names
    if result["active"] and result["active"] not in ("ufw", "firewalld", "nftables", "iptables"):
        result["active"] = None

    return result


def get_firewall_rules(tool: str = "") -> str:
    """获取指定防火墙的规则详情。"""
    if tool == "ufw":
        out, _ = run_cmd("sudo ufw status verbose 2>/dev/null")
        return out
    elif tool == "firewalld":
        out, _ = run_cmd("sudo firewall-cmd --list-all 2>/dev/null")
        return out
    elif tool == "nftables":
        # Show tuxtacklebox table first, then full ruleset
        out, _ = run_cmd(f"sudo nft list table inet {safe_quote(NFT_TABLE)} 2>/dev/null")
        if out.strip():
            full, _ = run_cmd("sudo nft list ruleset 2>/dev/null")
            return out + "\n\n--- Full ruleset ---\n" + full
        out, _ = run_cmd("sudo nft list ruleset 2>/dev/null")
        return out
    elif tool == "iptables":
        out, _ = run_cmd("sudo iptables -L -n -v 2>/dev/null")
        return out
    return ""


def fw_port_action(action: str, port: str, protocol: str) -> Tuple[bool, str]:
    """Add or remove a firewall port rule.

    Auto-detects the active firewall: ufw > firewalld > nftables > iptables.

    Args:
        action: 'allow' or 'deny'.
        port: Port number (1-65535).
        protocol: 'tcp' or 'udp'.

    Returns:
        (success, message) tuple.
    """
    port = str(port).strip()
    protocol = protocol.strip().lower()
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        return False, "Invalid port number (1-65535)"
    if protocol not in ("tcp", "udp"):
        return False, "Protocol must be tcp or udp"

    tools = _detect_firewall_tools()

    # UFW
    if tools['ufw']:
        out, code = run_cmd(f"sudo ufw {action} {port}/{protocol}", timeout=15)
        return code == 0, out

    # firewalld
    if tools['firewall-cmd']:
        fwd_action = "add-port" if action == "allow" else "remove-port"
        out, code = run_cmd(
            f"sudo firewall-cmd --permanent --{fwd_action}={port}/{protocol} 2>&1 && "
            f"sudo firewall-cmd --reload 2>&1",
            timeout=15
        )
        return code == 0, out

    # nftables – use idempotent helper with named table
    if tools['nft']:
        rule_body = f"{protocol} dport {port} accept"
        if action == "allow":
            ok, msg = nftables_add_rule(rule_body)
        else:
            ok, msg = nftables_delete_rule(rule_body)
        return ok, msg

    # iptables fallback
    ipt_action = "ACCEPT" if action == "allow" else "DROP"
    out, code = run_cmd(
        f"sudo iptables -{'A' if action == 'allow' else 'D'} INPUT -p {protocol} "
        f"--dport {port} -j {ipt_action} 2>&1",
        timeout=10
    )
    return code == 0, out


# ---------------------------------------------------------------------------
#  firewalld – service management & rich rules
# ---------------------------------------------------------------------------

def firewalld_add_service(service: str) -> Tuple[bool, str]:
    """Add a predefined firewalld service (http, https, ssh, nfs, etc.).

    Adds the service permanently and reloads firewalld.

    Args:
        service: Service name as known to firewalld, e.g. "http".

    Returns:
        (success, message) tuple.
    """
    _, code = run_cmd("which firewall-cmd 2>/dev/null")
    if code != 0:
        return False, "firewalld is not installed"

    # Check firewalld state
    state_out, sc = run_cmd("sudo firewall-cmd --state 2>/dev/null")
    if sc != 0:
        return False, f"firewalld is not running: {state_out.strip()}"

    out, code = run_cmd(
        f"sudo firewall-cmd --permanent --add-service={safe_quote(service.strip())} 2>&1 && "
        f"sudo firewall-cmd --reload 2>&1",
        timeout=15
    )
    return code == 0, out.strip()


def firewalld_remove_service(service: str) -> Tuple[bool, str]:
    """Remove a firewalld service permanently.

    Args:
        service: Service name.

    Returns:
        (success, message) tuple.
    """
    _, code = run_cmd("which firewall-cmd 2>/dev/null")
    if code != 0:
        return False, "firewalld is not installed"

    state_out, sc = run_cmd("sudo firewall-cmd --state 2>/dev/null")
    if sc != 0:
        return False, f"firewalld is not running: {state_out.strip()}"

    out, code = run_cmd(
        f"sudo firewall-cmd --permanent --remove-service={safe_quote(service.strip())} 2>&1 && "
        f"sudo firewall-cmd --reload 2>&1",
        timeout=15
    )
    return code == 0, out.strip()


def firewalld_add_rich_rule(rule: str) -> Tuple[bool, str]:
    """Add a firewalld rich rule (permanent + reload).

    Args:
        rule: A firewalld rich-rule string, e.g.
              'rule family="ipv4" source address="192.168.1.0/24" accept'.

    Returns:
        (success, message) tuple.
    """
    _, code = run_cmd("which firewall-cmd 2>/dev/null")
    if code != 0:
        return False, "firewalld is not installed"

    state_out, sc = run_cmd("sudo firewall-cmd --state 2>/dev/null")
    if sc != 0:
        return False, f"firewalld is not running: {state_out.strip()}"

    out, code = run_cmd(
        f"sudo firewall-cmd --permanent --add-rich-rule='{rule}' 2>&1 && "
        f"sudo firewall-cmd --reload 2>&1",
        timeout=15
    )
    return code == 0, out.strip()


def firewalld_set_default_zone(zone: str) -> Tuple[bool, str]:
    """Set the default firewalld zone.

    Args:
        zone: Zone name, e.g. "home", "public", "dmz", "trusted".

    Returns:
        (success, message) tuple.
    """
    zone = zone.strip()
    if not zone:
        return False, "Zone name is required"

    _, code = run_cmd("which firewall-cmd 2>/dev/null")
    if code != 0:
        return False, "firewalld is not installed"

    # Validate that the zone exists
    zones_out, _ = run_cmd("sudo firewall-cmd --get-zones 2>/dev/null")
    if zone not in zones_out.split():
        return False, f"Unknown zone '{zone}'. Available: {zones_out.strip()}"

    out, code = run_cmd(
        f"sudo firewall-cmd --set-default-zone={safe_quote(zone)} 2>&1",
        timeout=10
    )
    return code == 0, out.strip()


# ═══════════════════ firewalld 富规则与区域管理 ═══════════════════

def firewalld_list_rich_rules(zone: str = "") -> List[Dict]:
    """列出 firewalld 富规则。"""
    zone_opt = f"--zone={safe_quote(zone)}" if zone else ""
    out, _ = run_cmd(f"sudo firewall-cmd {zone_opt} --list-rich-rules 2>/dev/null")
    rules = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            rules.append({
                "raw": line,
                "zone": zone or "default",
                "family": "ipv4" if "ipv4" in line else ("ipv6" if "ipv6" in line else "any"),
                "action": "accept" if "accept" in line else ("reject" if "reject" in line else ("drop" if "drop" in line else "unknown")),
            })
    return rules


def firewalld_get_zones() -> Dict:
    """获取 firewalld 区域配置摘要。"""
    result: Dict = {"default_zone": "", "active_zones": [], "available_zones": [], "zones": []}
    def_out, _ = run_cmd("sudo firewall-cmd --get-default-zone 2>/dev/null")
    result["default_zone"] = def_out.strip()
    zones_out, _ = run_cmd("sudo firewall-cmd --get-zones 2>/dev/null")
    result["available_zones"] = sorted(zones_out.strip().split())
    active_out, _ = run_cmd("sudo firewall-cmd --get-active-zones 2>/dev/null")
    for line in active_out.splitlines():
        line = line.strip()
        if line and not line.startswith("interfaces:") and line in result["available_zones"]:
            result["active_zones"].append(line)
    for zone_name in result["available_zones"][:10]:
        svc_out, _ = run_cmd(f"sudo firewall-cmd --zone={safe_quote(zone_name)} --list-services 2>/dev/null")
        ports_out, _ = run_cmd(f"sudo firewall-cmd --zone={safe_quote(zone_name)} --list-ports 2>/dev/null")
        masq_out, _ = run_cmd(f"sudo firewall-cmd --zone={safe_quote(zone_name)} --query-masquerade 2>/dev/null")
        result["zones"].append({
            "name": zone_name, "services": svc_out.strip().split() if svc_out.strip() else [],
            "ports": ports_out.strip().split() if ports_out.strip() else [],
            "masquerade": masq_out.strip() == "yes", "is_default": zone_name == result["default_zone"],
        })
    return result
