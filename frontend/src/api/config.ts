import { api } from './request'
import type { ConfigPreset } from '@/types/api'

export const configApi = {
  getPresets: () => api<Record<string, ConfigPreset>>('/config/presets'),
  read: (path: string, preset?: string) => api<{ success: boolean; content: string; path: string; parsed?: Record<string, string> }>('/config/read', { method: 'POST', body: { path, preset } }),
  save: (path: string, content: string) => api<{ success: boolean; path: string }>('/config/save', { method: 'POST', body: { path, content } }),
  setParam: (path: string, key: string, value: string) => api<{ success: boolean; content: string }>('/config/setparam', { method: 'POST', body: { path, key, value } }),
}
