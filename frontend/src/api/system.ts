import { api } from './request'
import { useRequestCache } from '@/composables/useRequestCache'
import type {
  SystemInfo, TaskResponse, DistroInfo,
  SshConfig, SwapInfo, NtpStatus, UlimitsInfo,
  KernelModulesResponse, UsersResponse, MacStatus,
  ServiceOptimizeResponse, ServiceOptimizeResult,
  QuickParamsResponse,
  OptimizationProfileList, OptimizationPreview, OptimizationApplyResult,
  GrubConfig, CmdlinePresetsResponse,
  CpuGovernorInfo, IoSchedulerInfo,
} from '@/types/api'

export type { SshConfig, SwapInfo }

export const systemApi = {
  getInfo: () => api<SystemInfo>('/system/info'),
  getDistro: () => api<DistroInfo>('/system/distro'),
  /** Cached wrapper for getDistro — use this to avoid duplicate requests */
  getDistroCached: () => useRequestCache<DistroInfo>('distro', () => api<DistroInfo>('/system/distro'), 60000),
  getTimezones: () => api<string[]>('/system/timezones'),
  getLocales: () => api<string[]>('/system/locales'),
  setHostname: (hostname: string) => api<{ success: boolean; message: string }>('/system/hostname', { method: 'POST', body: { hostname } }),
  setTimezone: (timezone: string) => api<{ success: boolean; message: string }>('/system/timezone', { method: 'POST', body: { timezone } }),
  setLocale: (locale: string) => api<{ success: boolean; message: string }>('/system/locale', { method: 'POST', body: { locale } }),
  getSysctl: (q?: string) => api<Record<string, string>>(`/sysctl${q ? `?q=${q}` : ''}`),
  setSysctl: (key: string, value: string) => api<{ success: boolean; message: string }>('/sysctl/set', { method: 'POST', body: { key, value } }),
  persistSysctl: (key: string, value: string) => api<{ success: boolean; message: string }>('/sysctl/persist', { method: 'POST', body: { key, value } }),
  getHosts: () => api<{ content: string }>('/hosts'),
  saveHosts: (content: string) => api<{ success: boolean }>('/hosts/save', { method: 'POST', body: { content } }),
  getSshConfig: () => api<SshConfig>('/system/ssh'),
  saveSshConfig: (config: SshConfig) => api<{ success: boolean }>('/system/ssh', { method: 'POST', body: { config } }),
  getSwapInfo: () => api<SwapInfo>('/system/swap'),
  createSwap: (size: string) => api<{ success: boolean; message: string }>('/system/swap/create', { method: 'POST', body: { size } }),
  disableSwap: () => api<{ success: boolean; message: string }>('/system/swap/disable', { method: 'POST' }),
  update: () => api<TaskResponse>('/system/update', { method: 'POST' }),
  // NTP
  getNtpStatus: () => api<NtpStatus>('/system/ntp'),
  toggleNtp: (enable: boolean) => api<{ success: boolean; message: string }>('/system/ntp', { method: 'POST', body: { enable } }),
  // Ulimits
  getUlimits: () => api<UlimitsInfo>('/system/ulimits'),
  saveUlimits: (content: string) => api<{ success: boolean; message: string }>('/system/ulimits', { method: 'POST', body: { content } }),
  // Kernel Modules
  getModules: () => api<KernelModulesResponse>('/system/modules'),
  manageModule: (name: string, action: string) => api<{ success: boolean; message: string }>('/system/modules/manage', { method: 'POST', body: { name, action } }),
  // Users
  getUsers: () => api<UsersResponse>('/system/users'),
  addUser: (username: string, password: string, groups?: string, shell?: string) =>
    api<{ success: boolean; message: string }>('/system/users/add', { method: 'POST', body: { username, password, groups: groups || '', shell: shell || '/bin/bash' } }),
  deleteUser: (username: string) => api<{ success: boolean; message: string }>('/system/users/delete', { method: 'POST', body: { username } }),
  changePassword: (username: string, password: string) => api<{ success: boolean; message: string }>('/system/users/password', { method: 'POST', body: { username, password } }),
  // Journal Logs
  getJournalLogs: (lines?: number, unit?: string, priority?: string) =>
    api<{ logs: string }>(`/system/logs?lines=${lines || 100}&unit=${unit || ''}&priority=${priority || ''}`),
  // Service Optimization
  getServiceOptimize: () => api<ServiceOptimizeResponse>('/system/service-optimize'),
  runServiceOptimize: (svcNames?: string[]) =>
    api<ServiceOptimizeResult>('/system/service-optimize', { method: 'POST', body: svcNames ? { svc_names: svcNames } : {} }),
  // Quick Kernel Params
  getQuickParams: () => api<QuickParamsResponse>('/system/quick-params'),
  applyQuickParams: (params: Record<string, string>) =>
    api<{ results: Array<{ key: string; success: boolean; message: string }> }>('/system/quick-params', { method: 'POST', body: { params } }),
  // Optimization Profiles
  getOptimizationProfiles: () => api<OptimizationProfileList>('/system/optimization-profiles'),
  getOptimizationPreview: (profile: string) => api<OptimizationPreview>(`/system/optimization-preview?profile=${profile}`),
  applyOptimizationProfile: (profile: string, sysctlKeys?: string[], svcNames?: string[]) =>
    api<OptimizationApplyResult>('/system/optimization-apply', { method: 'POST', body: { profile, sysctl_keys: sysctlKeys, svc_names: svcNames } }),
  // Boot & Kernel
  getGrubConfig: (bootloader?: string) => api<GrubConfig>(`/system/grub-config${bootloader ? `?bootloader=${bootloader}` : ''}`),
  getBootloaders: () => api<{ bootloaders: string[] }>('/system/bootloaders'),
  setGrubDefault: (value: string) => api<{ success: boolean; message: string }>('/system/grub-default', { method: 'POST', body: { value } }),
  setGrubCmdline: (params: string) => api<{ success: boolean; message: string }>('/system/grub-cmdline', { method: 'POST', body: { params } }),
  getCmdlinePresets: () => api<CmdlinePresetsResponse>('/system/grub-cmdline-presets'),
  getCpuGovernor: () => api<CpuGovernorInfo>('/system/cpu-governor'),
  setCpuGovernor: (governor: string) => api<{ success: boolean; message: string }>('/system/cpu-governor', { method: 'POST', body: { governor } }),
  getIoScheduler: () => api<IoSchedulerInfo>('/system/io-scheduler'),
  setIoScheduler: (device: string, scheduler: string) => api<{ success: boolean; message: string }>('/system/io-scheduler', { method: 'POST', body: { device, scheduler } }),
  // Cron
  getCrontab: (user?: string) => api<{ content: string; user: string }>(`/system/crontab${user ? `?user=${user}` : ''}`),
  setCrontab: (content: string, user?: string) => api<{ success: boolean; message: string }>('/system/crontab', { method: 'POST', body: { content, user } }),
  // Logs
  getDmesg: (lines?: number, level?: string) => api<{ logs: string }>(`/system/dmesg?lines=${lines || 200}&level=${level || ''}`),
  getAuditLogs: (lines?: number) => api<{ logs: string }>(`/system/audit?lines=${lines || 100}`),
  // MAC / SELinux
  getMacStatus: () => api<MacStatus>('/system/mac'),
  setSelinux: (mode: string) => api<{ success: boolean; message: string }>('/system/selinux', { method: 'POST', body: { mode } }),
  // Grub repair & initramfs
  grubRepair: (disk?: string, root?: string) => api<TaskResponse>('/system/grub-repair', { method: 'POST', body: { disk, root } }),
  rebuildInitramfs: (all?: boolean) => api<TaskResponse>('/system/initramfs-rebuild', { method: 'POST', body: { all } }),
  getDiagnostic: () => api<{ success: boolean; report: string }>("/system/diagnostic"),
  getFeatures: () => api<Record<string, any>>('/system/features'),
  getThermal: () => api<{ cpu_temp: number | null; fans: any[] }>('/system/thermal'),
  getNotifications: () => api<{ events: string[] }>('/system/notifications'),
  getCpuFreq: () => api<any>('/system/cpu-freq'),
  // Process management
  getProcesses: (sort?: string, filter?: string, limit?: number) => api<{ processes: any[] }>(`/system/processes?sort=${sort||'cpu'}&filter=${filter||''}&limit=${limit||100}`),
  getProcessTree: () => api<any>('/system/processes/tree'),
  getTopProcesses: (limit?: number) => api<any>(`/system/processes/top?limit=${limit||10}`),
  getProcessDetail: (pid: number) => api<any>(`/system/processes/${pid}`),
  getSystemLoad: () => api<any>('/system/processes/load'),
  killProcess: (pid: number, signal?: string) => api<{ success: boolean; message: string }>('/system/processes/kill', { method: 'POST', body: { pid, signal } }),
  reniceProcess: (pid: number, nice: number) => api<{ success: boolean; message: string }>('/system/processes/renice', { method: 'POST', body: { pid, nice } }),
  // Timers & cron
  getTimers: () => api<{ timers: any[]; count: number }>('/system/timers'),
  getTimerDetail: (name: string) => api<any>(`/system/timers/${encodeURIComponent(name)}`),
  timerAction: (name: string, action: string) => api<{ success: boolean; message: string }>('/system/timers/action', { method: 'POST', body: { name, action } }),
  getCrontabParsed: () => api<{ entries: any[]; count: number }>('/system/crontab/parsed'),
  getSystemCrontabs: () => api<any>('/system/crontab/system'),
  // Kernel profiles
  getKernelProfiles: () => api<{ profiles: any[] }>('/system/kernel-profiles'),
  saveKernelProfile: (name: string) => api<any>('/system/kernel-profiles/save', { method: 'POST', body: { name } }),
  loadKernelProfile: (name: string) => api<any>(`/system/kernel-profiles/load?name=${encodeURIComponent(name)}`),
  applyKernelProfile: (name: string) => api<{ success: boolean; applied: number }>('/system/kernel-profiles/apply', { method: 'POST', body: { name } }),
  deleteKernelProfile: (name: string) => api<{ success: boolean; message: string }>('/system/kernel-profiles/delete', { method: 'POST', body: { name } }),
  compareKernelProfile: (name: string) => api<any>(`/system/kernel-profiles/compare?name=${encodeURIComponent(name)}`),
}
