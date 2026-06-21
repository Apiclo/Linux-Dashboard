import { api } from './request'
import type {
  TaskResponse, SoftwareCatalog,
  InstalledPackagesResponse, ReposResponse, UpdateHistoryItem,
  SearchPackageResult,
} from '@/types/api'

export const packagesApi = {
  getSoftware: () => api<SoftwareCatalog>('/packages/software'),
  search: (q: string) => api<{ result: string }>(`/packages/search?q=${encodeURIComponent(q)}`),
  searchStructured: (q: string) => api<{ results: SearchPackageResult[] }>(`/packages/search-structured?q=${encodeURIComponent(q)}`),
  install: (pkg: string) => api<TaskResponse>('/packages/install', { method: 'POST', body: { package: pkg } }),
  remove: (pkg: string) => api<TaskResponse>('/packages/remove', { method: 'POST', body: { package: pkg } }),
  // Installed packages
  getInstalled: (q?: string) => api<InstalledPackagesResponse>(`/packages/installed${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  // Repos
  getRepos: () => api<ReposResponse>('/packages/repos'),
  addRepo: (url: string) => api<{ success: boolean; message: string }>('/packages/repo/add', { method: 'POST', body: { url } }),
  removeRepo: (path: string) => api<{ success: boolean; message: string }>('/packages/repo/remove', { method: 'POST', body: { path } }),
  // Batch
  batchInstall: (packages: string[]) => api<TaskResponse>('/packages/batch/install', { method: 'POST', body: { packages } }),
  batchRemove: (packages: string[]) => api<TaskResponse>('/packages/batch/remove', { method: 'POST', body: { packages } }),
  batchUpdate: () => api<TaskResponse>('/packages/batch/update', { method: 'POST' }),
  // History
  getUpdateHistory: () => api<{ history: UpdateHistoryItem[] }>('/packages/update-history'),
  // Repo raw
  getRepoRaw: () => api<{ manager: string; files: Record<string, string> }>('/packages/repo-raw'),
  saveRepoRaw: (file: string, content: string) => api<{ success: boolean; message: string }>('/packages/repo-raw', { method: 'POST', body: { file, content } }),
  // Cleanup
  getOrphans: () => api<{ orphans: any[]; suggestions: any[] }>('/packages/orphans'),
  cleanCache: () => api<{ before: string; after: string; freed: string }>('/packages/cleanup-cache', { method: 'POST' }),
  getPackageFiles: (pkg: string) => api<{ files: string[]; total: number }>(`/packages/files/${encodeURIComponent(pkg)}`),
}
