import { api } from './request'
import type { BlockDevice, TaskResponse } from '@/types/api'

export const diskApi = {
  getDevices: () => api<BlockDevice[]>('/disk/devices'),
  getUsage: () => api<{ usage: string }>('/disk/usage'),
  getFstab: () => api<{ content: string }>('/disk/fstab'),
  saveFstab: (content: string) => api<{ success: boolean }>('/disk/fstab/save', { method: 'POST', body: { content } }),
  mount: (device: string, mountpoint: string, fstype?: string) => api<{ success: boolean; message: string }>('/disk/mount', { method: 'POST', body: { device, mountpoint, fstype } }),
  umount: (target: string) => api<{ success: boolean; message: string }>('/disk/umount', { method: 'POST', body: { target } }),
  // RAID
  getRaidArrays: () => api<{ arrays: any[] }>('/raid/arrays'),
  getRaidDevices: () => api<{ devices: any[] }>('/raid/devices'),
  createRaid: (level: string, devices: string[], name?: string) => api('/raid/create', { method: 'POST', body: { level, devices, name } }),
  manageRaid: (device: string, action: string) => api('/raid/manage', { method: 'POST', body: { device, action } }),
  getRaidDetail: (device: string) => api<{ success: boolean; detail: string }>(`/raid/detail?device=${encodeURIComponent(device)}`),
}
