"""Network operations package."""
from core.network.interfaces import (
    get_network_interfaces,
    get_dns,
    set_dns,
    detect_network_manager,
    get_interface_ip_mode,
    get_ip_config,
    set_static_ip,
    set_dhcp,
    get_listen_ports,
    get_network_traffic,
)
from core.network.firewall import (
    firewalld_add_rich_rule,
    firewalld_add_service,
    firewalld_remove_service,
    firewalld_set_default_zone,
    firewalld_list_rich_rules,
    firewalld_get_zones,
    fw_port_action,
    get_firewall_status,
    get_firewall_rules,
    nftables_add_rule,
    nftables_delete_rule,
)
from core.network.bonding import (
    BOND_MODES,
    BOND_OPTIONS,
    get_bonds,
    create_bond,
    delete_bond,
    get_available_slaves,
    get_bond_options,
    create_bond_advanced,
)
from core.network.vlan_bridge import (
    get_vlans,
    create_vlan,
    delete_vlan,
    get_bridges,
    create_bridge,
    bridge_add_member,
    bridge_remove_member,
    delete_bridge,
)
from core.network.routes import (
    get_routes,
    add_route,
    delete_route,
)
from core.network.diagnostics import (
    ping_host,
    traceroute_host,
    dns_lookup,
    port_scan,
    check_connectivity,
)
from core.network.wireguard import (
    get_wireguard_interfaces,
    wireguard_check,
    create_wireguard,
    delete_wireguard,
)

__all__ = [
    # interfaces
    "get_network_interfaces",
    "get_dns",
    "set_dns",
    "detect_network_manager",
    "get_interface_ip_mode",
    "get_ip_config",
    "set_static_ip",
    "set_dhcp",
    "get_listen_ports",
    "get_network_traffic",
    # firewall
    "firewalld_add_rich_rule",
    "firewalld_add_service",
    "firewalld_remove_service",
    "firewalld_set_default_zone",
    "firewalld_list_rich_rules",
    "firewalld_get_zones",
    "fw_port_action",
    "get_firewall_status",
    "get_firewall_rules",
    "nftables_add_rule",
    "nftables_delete_rule",
    # bonding
    "BOND_MODES",
    "BOND_OPTIONS",
    "get_bonds",
    "create_bond",
    "delete_bond",
    "get_available_slaves",
    "get_bond_options",
    "create_bond_advanced",
    # vlan_bridge
    "get_vlans",
    "create_vlan",
    "delete_vlan",
    "get_bridges",
    "create_bridge",
    "bridge_add_member",
    "bridge_remove_member",
    "delete_bridge",
    # routes
    "get_routes",
    "add_route",
    "delete_route",
    # wireguard
    "get_wireguard_interfaces",
    "wireguard_check",
    "create_wireguard",
    "delete_wireguard",
]
