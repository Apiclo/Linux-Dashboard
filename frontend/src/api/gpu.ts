import { api, uploadFile } from './request'
import type {
  GpuDetectData, NvidiaVersion, TaskResponse, OfflinePackage,
  CompatResult, DistroInfo,
} from '@/types/api'

export const gpuApi = {
  detect: () => api<GpuDetectData>('/gpu/detect'),
  getDistro: () => api<DistroInfo>('/gpu/distro'),
  getNvidiaVersions: () => api<NvidiaVersion[]>('/gpu/nvidia/versions'),
  getCudaVersions: () => api<string[]>('/gpu/cuda/versions'),
  getCompatibility: () => api<CompatResult>('/gpu/compatibility'),
  blacklistNouveau: () => api<{ success: boolean; message: string }>('/gpu/nouveau/blacklist', { method: 'POST' }),
  installRepo: (params: Record<string, any>) => api<TaskResponse>('/gpu/install/repo', { method: 'POST', body: params }),
  installRunfile: (params: Record<string, any>) => api<TaskResponse>('/gpu/install/runfile', { method: 'POST', body: params }),
  installAmd: () => api<TaskResponse>('/gpu/install/amd', { method: 'POST' }),
  installIntel: () => api<TaskResponse>('/gpu/install/intel', { method: 'POST' }),
  installRocm: (usecase?: string) => api<TaskResponse>('/gpu/install/rocm', { method: 'POST', body: { usecase: usecase || 'rocm' } }),
  installCustom: (cmd: string) => api<TaskResponse>('/gpu/install/custom', { method: 'POST', body: { cmd } }),
  setupCudaRepo: () => api<TaskResponse>('/gpu/cuda/setup-repo', { method: 'POST' }),
  installCuda: (method: string, version: string) => api<TaskResponse>('/gpu/cuda/install', { method: 'POST', body: { method, version } }),
  uninstall: () => api<TaskResponse>('/gpu/uninstall', { method: 'POST' }),
  validateRunfile: (path: string) => api<{ success: boolean; message: string }>('/gpu/runfile/validate', { method: 'POST', body: { path } }),
  getOfflineList: () => api<OfflinePackage[]>('/gpu/offline/list'),
  offlineInstall: (params: Record<string, any>) => api<TaskResponse>('/gpu/offline/install', { method: 'POST', body: params }),
  offlineInspect: (extractDir: string) =>
    api<{ success: boolean; meta: Record<string, any> }>('/gpu/offline/inspect', { method: 'POST', body: { extract_dir: extractDir } }),
  offlineDelete: (path: string) => api<{ success: boolean; message: string }>('/gpu/offline/delete', { method: 'POST', body: { path } }),
  getNvidiaPackages: () => api<Array<{ package: string; version?: string; description: string }>>('/offline/nvidia-packages'),
  generateOffline: (params: Record<string, any>) => api<TaskResponse>('/offline/generate', { method: 'POST', body: params }),
  getGeneratedList: () => api<OfflinePackage[]>('/offline/generated-list'),
  uploadRunfile: (file: File) =>
    uploadFile<{ success: boolean; path: string; filename: string; size: number; message?: string }>('/upload/runfile', file),
  uploadOffline: (file: File) =>
    uploadFile<{ success: boolean; extract_dir?: string; path?: string; name?: string; meta?: Record<string, any>; package_count?: number; has_install_script?: boolean; size?: number; message?: string }>('/upload/offline', file),
  getNvidiaSmiRealtime: () => api<{ data: string }>('/gpu/nvidia-smi/realtime'),
  startNvidiaMonitor: () => api<TaskResponse>('/gpu/nvidia-smi/monitor', { method: 'POST' }),
}
