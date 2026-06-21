import { api } from './request'
import type { ServiceInfo, TaskResponse } from '@/types/api'

export const servicesApi = {
  getServices: () => api<ServiceInfo[]>('/services'),
  action: (name: string, action: string) => api<{ success: boolean; message: string }>('/service/action', { method: 'POST', body: { name, action } }),
  getLogs: (name: string, lines = 100) => api<{ logs: string }>(`/service/logs/${name}?lines=${lines}`),
}
