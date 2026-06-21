import { api } from './request'
import type { NetworkInterface, PortInfo, TaskResponse } from '@/types/api'

export const networkApi = {
  getInterfaces: () => api<NetworkInterface[]>('/network/interfaces'),
  getDns: () => api<{ dns: string[] }>('/network/dns'),
  setDns: (servers: string[]) => api<{ success: boolean; message: string }>('/network/dns', { method: 'POST', body: { servers } }),
  getFirewall: () => api<{ name: string; status: string }>('/network/firewall'),
  // @deprecated — use interfaceAction / fwAllow / fwDeny for structured operations
  runFwCmd: (cmd: string) => api<{ success: boolean; message: string }>('/network/fwcmd', { method: 'POST', body: { cmd } }),
  getPorts: () => api<{ ports: PortInfo[] }>('/network/ports'),
  // Semantic endpoints
  interfaceAction: (name: string, action: 'up' | 'down' | 'restart') => api<{ success: boolean; message: string }>('/network/interface/action', { method: 'POST', body: { name, action } }),
  fwAllow: (port: string, protocol: string) => api<{ success: boolean; message: string }>('/network/firewall/allow', { method: 'POST', body: { port, protocol } }),
  fwDeny: (port: string, protocol: string) => api<{ success: boolean; message: string }>('/network/firewall/deny', { method: 'POST', body: { port, protocol } }),
}
