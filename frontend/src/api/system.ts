import { api } from './request'
import type { SystemInfo, TaskResponse, DistroInfo } from '@/types/api'

export interface SshConfig {
  port: string
  permit_root_login: string
  password_auth: string
  pubkey_auth: string
}

export interface SwapInfo {
  total: string
  used: string
  free: string
  files: Array<{ path: string; type: string; size_kb: string; used_kb: string }>
}

export const systemApi = {
  getInfo: () => api<SystemInfo>('/system/info'),
  getDistro: () => api<DistroInfo>('/system/distro'),
  getTimezones: () => api<string[]>('/system/timezones'),
  getLocales: () => api<string[]>('/system/locales'),
  setHostname: (hostname: string) => api('/system/hostname', { method: 'POST', body: { hostname } }),
  setTimezone: (timezone: string) => api('/system/timezone', { method: 'POST', body: { timezone } }),
  setLocale: (locale: string) => api('/system/locale', { method: 'POST', body: { locale } }),
  getSysctl: (q?: string) => api<Record<string, string>>(`/sysctl${q ? `?q=${q}` : ''}`),
  setSysctl: (key: string, value: string) => api('/sysctl/set', { method: 'POST', body: { key, value } }),
  getHosts: () => api<{ content: string }>('/hosts'),
  saveHosts: (content: string) => api('/hosts/save', { method: 'POST', body: { content } }),
  getSshConfig: () => api<SshConfig>('/system/ssh'),
  saveSshConfig: (config: SshConfig) => api('/system/ssh', { method: 'POST', body: { config } }),
  getSwapInfo: () => api<SwapInfo>('/system/swap'),
  createSwap: (size: string) => api('/system/swap/create', { method: 'POST', body: { size } }),
  update: () => api<TaskResponse>('/system/update', { method: 'POST' }),
  // NTP
  getNtpStatus: () => api<{ ntp_enabled: boolean; synced: boolean; service?: string }>('/system/ntp'),
  toggleNtp: (enable: boolean) => api('/system/ntp', { method: 'POST', body: { enable } }),
  // Ulimits
  getUlimits: () => api<{ file: string; running: string }>('/system/ulimits'),
  saveUlimits: (content: string) => api('/system/ulimits', { method: 'POST', body: { content } }),
  // Kernel Modules
  getModules: () => api<{ modules: Array<{ name: string; size: string; used_by: number; used_by_list: string }> }>('/system/modules'),
  manageModule: (name: string, action: string) => api('/system/modules/manage', { method: 'POST', body: { name, action } }),
  // Swap Disable
  disableSwap: () => api<{ success: boolean; message: string }>('/system/swap/disable', { method: 'POST' }),
  // Users
  getUsers: () => api<{ users: Array<{ username: string; uid: number; gid: number; home: string; shell: string }> }>('/system/users'),
  addUser: (username: string, password: string, groups?: string, shell?: string) => api('/system/users/add', { method: 'POST', body: { username, password, groups: groups || '', shell: shell || '/bin/bash' } }),
  deleteUser: (username: string) => api('/system/users/delete', { method: 'POST', body: { username } }),
  changePassword: (username: string, password: string) => api('/system/users/password', { method: 'POST', body: { username, password } }),
  // Journal Logs
  getJournalLogs: (lines?: number, unit?: string, priority?: string) => api<{ logs: string }>(`/system/logs?lines=${lines || 100}&unit=${unit || ''}&priority=${priority || ''}`),
  // Service Optimization
  getServiceOptimize: () => api<{ services: Array<{ name: string; desc: string; safe: boolean; enabled: boolean; active: boolean }> }>('/system/service-optimize'),
  runServiceOptimize: () => api<{ results: Array<{ name: string; success: boolean }> }>('/system/service-optimize', { method: 'POST' }),
  // Quick Kernel Params
  getQuickParams: () => api<{ params: Array<{ key: string; current: string; desc: string; recommended: string; type: string }> }>('/system/quick-params'),
  applyQuickParams: (params: Record<string, string>) => api('/system/quick-params', { method: 'POST', body: { params } }),
  // Optimization Profiles
  getOptimizationProfiles: () => api<{ profiles: Record<string, { label: string; desc: string }> }>('/system/optimization-profiles'),
  getOptimizationPreview: (profile: string) => api<{
    success: boolean; profile: string; label: string; desc: string
    sysctl_changes: Array<{ key: string; current: string; recommended: string; will_change: boolean }>
    svc_changes: Array<{ name: string; enabled: boolean; active: boolean; will_disable: boolean }>
  }>(`/system/optimization-preview?profile=${profile}`),
  applyOptimizationProfile: (profile: string, sysctlKeys?: string[], svcNames?: string[]) => api<{
    success: boolean; profile: string
    sysctl_results: Array<{ key: string; success: boolean; message: string }>
    svc_results: Array<{ name: string; success: boolean }>
  }>('/system/optimization-apply', { method: 'POST', body: { profile, sysctl_keys: sysctlKeys, svc_names: svcNames } }),
  // Boot & Kernel
  getGrubConfig: () => api<{
    default: string; timeout: string; cmdline: string
    entries: Array<{ index: number; title: string; file?: string }>
    config_file: string; grub_cfg_path: string; mkconfig_cmd: string
  }>('/system/grub-config'),
  setGrubDefault: (value: string) => api<{ success: boolean; message: string }>('/system/grub-default', { method: 'POST', body: { value } }),
  setGrubCmdline: (params: string) => api<{ success: boolean; message: string }>('/system/grub-cmdline', { method: 'POST', body: { params } }),
  getCmdlinePresets: () => api<{ presets: Record<string, { label: string; params: string; desc: string }> }>('/system/grub-cmdline-presets'),
  getCpuGovernor: () => api<{ available: string[]; current: string; driver: string }>('/system/cpu-governor'),
  setCpuGovernor: (governor: string) => api<{ success: boolean; message: string }>('/system/cpu-governor', { method: 'POST', body: { governor } }),
  getIoScheduler: () => api<{ devices: Array<{ name: string; current: string; available: string[] }> }>('/system/io-scheduler'),
  setIoScheduler: (device: string, scheduler: string) => api<{ success: boolean; message: string }>('/system/io-scheduler', { method: 'POST', body: { device, scheduler } }),
}
