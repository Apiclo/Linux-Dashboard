import { api } from './request'
import type {
  NetworkInterface, PortInfo, TaskResponse,
  FirewallStatus, BondsResponse, BondOptionDef,
  VlanInfo, BridgeInfo, RouteInfo, WireGuardInfo, WireGuardCheckResult,
} from '@/types/api'

export const networkApi = {
  getInterfaces: () => api<NetworkInterface[]>('/network/interfaces'),
  getDns: () => api<{ dns: string[] }>('/network/dns'),
  setDns: (servers: string[]) => api<{ success: boolean; message: string }>('/network/dns', { method: 'POST', body: { servers } }),
  getFirewall: () => api<FirewallStatus>('/network/firewall'),
  getFirewallRules: (tool: string) => api<{ rules: string }>(`/network/firewall/rules?tool=${tool}`),
  getNetworkManager: () => api<{ manager: string }>('/network/manager'),
  // @deprecated — use interfaceAction / fwAllow / fwDeny for structured operations
  runFwCmd: (cmd: string) => api<{ success: boolean; message: string }>('/network/fwcmd', { method: 'POST', body: { cmd } }),
  getPorts: () => api<{ ports: PortInfo[] }>('/network/ports'),
  // Semantic endpoints
  interfaceAction: (name: string, action: 'up' | 'down' | 'restart') =>
    api<{ success: boolean; message: string }>('/network/interface/action', { method: 'POST', body: { name, action } }),
  fwAllow: (port: string, protocol: string) =>
    api<{ success: boolean; message: string }>('/network/firewall/allow', { method: 'POST', body: { port, protocol } }),
  fwDeny: (port: string, protocol: string) =>
    api<{ success: boolean; message: string }>('/network/firewall/deny', { method: 'POST', body: { port, protocol } }),
  // IP config
  setStaticIp: (iface: string, address: string, netmask?: string, gateway?: string, dns?: string) =>
    api<{ success: boolean; message: string }>('/network/ip/static', { method: 'POST', body: { interface: iface, address, netmask, gateway, dns } }),
  setDhcp: (iface: string) => api<{ success: boolean; message: string }>('/network/ip/dhcp', { method: 'POST', body: { interface: iface } }),
  getIfaceIpMode: (iface: string) => api<{ mode: string; netmask: string; gateway: string; dns: string }>(`/network/ip-config/${iface}`),
  getTraffic: () => api<{ interfaces: any[]; total_rx: number; total_tx: number }>('/network/traffic'),
  getFirewallZones: () => api<any>('/network/firewall/zones'),
  getFirewallRichRules: (zone?: string) => api<{ rules: any[] }>(`/network/firewall/rich-rules${zone ? `?zone=${zone}` : ''}`),
  // Diagnostics
  diagPing: (host: string, count?: number) => api<any>(`/network/diag/ping?host=${encodeURIComponent(host)}&count=${count||4}`),
  diagTraceroute: (host: string) => api<any>(`/network/diag/traceroute?host=${encodeURIComponent(host)}`),
  diagDns: (domain: string, type?: string) => api<any>(`/network/diag/dns?domain=${encodeURIComponent(domain)}&type=${type||'A'}`),
  diagPortscan: (host: string, ports?: string) => api<any>(`/network/diag/portscan?host=${encodeURIComponent(host)}&ports=${ports||''}`),
  diagConnectivity: (target?: string) => api<any>(`/network/diag/connectivity${target ? `?target=${target}` : ''}`),

  // Bonding
  getBonds: () => api<BondsResponse>('/network/bonds'),
  createBond: (name: string, slaves: string[], mode?: string, ip?: string, gateway?: string) =>
    api<{ success: boolean; message: string }>('/network/bond/create', { method: 'POST', body: { name, slaves, mode, ip, gateway } }),
  deleteBond: (name: string) => api<{ success: boolean; message: string }>('/network/bond/delete', { method: 'POST', body: { name } }),
  getBondOptions: () => api<{ options: Record<string, BondOptionDef> }>('/network/bond/options'),
  createBondAdvanced: (name: string, slaves: string[], mode?: string, options?: Record<string, string>) =>
    api<{ success: boolean; message: string }>('/network/bond/create-advanced', { method: 'POST', body: { name, slaves, mode, options } }),
  // VLAN
  getVlans: () => api<{ vlans: VlanInfo[] }>('/network/vlans'),
  createVlan: (parent: string, vlan_id: number, name?: string) =>
    api<{ success: boolean; message: string }>('/network/vlan/create', { method: 'POST', body: { parent, vlan_id, name } }),
  deleteVlan: (name: string) => api<{ success: boolean; message: string }>('/network/vlan/delete', { method: 'POST', body: { name } }),
  // Bridge
  getBridges: () => api<{ bridges: BridgeInfo[] }>('/network/bridges'),
  createBridge: (name: string) => api<{ success: boolean; message: string }>('/network/bridge/create', { method: 'POST', body: { name } }),
  bridgeAddMember: (bridge: string, iface: string) =>
    api<{ success: boolean; message: string }>('/network/bridge/add-member', { method: 'POST', body: { bridge, interface: iface } }),
  bridgeRemoveMember: (iface: string) =>
    api<{ success: boolean; message: string }>('/network/bridge/remove-member', { method: 'POST', body: { interface: iface } }),
  deleteBridge: (name: string) => api<{ success: boolean; message: string }>('/network/bridge/delete', { method: 'POST', body: { name } }),
  // Routes
  getRoutes: () => api<{ routes: RouteInfo[] }>('/network/routes'),
  addRoute: (dst: string, gateway?: string, dev?: string, metric?: string) =>
    api<{ success: boolean; message: string }>('/network/route/add', { method: 'POST', body: { dst, gateway, dev, metric } }),
  deleteRoute: (dst: string, gateway?: string) =>
    api<{ success: boolean; message: string }>('/network/route/delete', { method: 'POST', body: { dst, gateway } }),
  // WireGuard
  checkWireguard: () => api<WireGuardCheckResult>('/network/wireguard/check'),
  getWireguardList: () => api<{ interfaces: WireGuardInfo[] }>('/network/wireguard/list'),
  createWireguard: (name: string) => api<{ success: boolean; message: string }>('/network/wireguard/create', { method: 'POST', body: { name } }),
  deleteWireguard: (name: string) => api<{ success: boolean; message: string }>('/network/wireguard/delete', { method: 'POST', body: { name } }),
}
