import { api } from './request'
import type { TaskResponse } from '@/types/api'

export const packagesApi = {
  getSoftware: () => api<Record<string, Record<string, any>>>('/packages/software'),
  search: (q: string) => api<{ result: string }>(`/packages/search?q=${encodeURIComponent(q)}`),
  install: (pkg: string) => api<TaskResponse>('/packages/install', { method: 'POST', body: { package: pkg } }),
  remove: (pkg: string) => api<TaskResponse>('/packages/remove', { method: 'POST', body: { package: pkg } }),
}
