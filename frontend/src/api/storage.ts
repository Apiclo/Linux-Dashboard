import { api } from './request'
import type {
  LvmStatus, BtrfsStatus, FsInfo, SmartDevice,
  LuksStatus, LuksDeviceInfo, ZfsStatus, ZfsDatasetInfo,
  TaskResponse,
} from '@/types/api'

export const storageApi = {
  // LVM
  getLvmStatus: () => api<LvmStatus>('/storage/lvm'),
  createPv: (device: string) => api<{ success: boolean; message: string }>('/storage/lvm/pv', { method: 'POST', body: { device } }),
  createVg: (name: string, devices: string[]) => api<{ success: boolean; message: string }>('/storage/lvm/vg', { method: 'POST', body: { name, devices } }),
  extendVg: (name: string, devices: string[]) => api<{ success: boolean; message: string }>('/storage/lvm/vg/extend', { method: 'POST', body: { name, devices } }),
  createLv: (name: string, vg: string, size: string) => api<{ success: boolean; message: string }>('/storage/lvm/lv', { method: 'POST', body: { name, vg, size } }),
  resizeLv: (path: string, size: string) => api<{ success: boolean; message: string }>('/storage/lvm/lv/resize', { method: 'POST', body: { path, size } }),
  removeLv: (path: string) => api<{ success: boolean; message: string }>('/storage/lvm/lv/remove', { method: 'POST', body: { path } }),
  createThinPool: (name: string, vg: string, size: string) => api<{ success: boolean; message: string }>('/storage/lvm/thin-pool', { method: 'POST', body: { name, vg, size } }),
  createThinLv: (name: string, vg: string, pool: string, size: string) => api<{ success: boolean; message: string }>('/storage/lvm/thin-lv', { method: 'POST', body: { name, vg, pool, size } }),
  createLvSnapshot: (lv_path: string, snap_name: string, size?: string) => api<{ success: boolean; message: string }>('/storage/lvm/snapshot', { method: 'POST', body: { lv_path, snap_name, size } }),
  removeVg: (name: string) => api<{ success: boolean; message: string }>('/storage/lvm/vg/remove', { method: 'POST', body: { name } }),
  removePv: (device: string) => api<{ success: boolean; message: string }>('/storage/lvm/pv/remove', { method: 'POST', body: { device } }),
  // Btrfs
  getBtrfsStatus: () => api<BtrfsStatus>('/storage/btrfs'),
  createSubvolume: (path: string) => api<{ success: boolean; message: string }>('/storage/btrfs/subvolume', { method: 'POST', body: { path } }),
  deleteSubvolume: (path: string) => api<{ success: boolean; message: string }>('/storage/btrfs/subvolume/delete', { method: 'POST', body: { path } }),
  createSnapshot: (source: string, dest: string, readonly?: boolean) => api<{ success: boolean; message: string }>('/storage/btrfs/snapshot', { method: 'POST', body: { source, dest, readonly } }),
  btrfsScrub: (mount: string) => api<{ success: boolean; message: string }>('/storage/btrfs/scrub', { method: 'POST', body: { mount } }),
  btrfsDefrag: (mount: string) => api<{ success: boolean; message: string }>('/storage/btrfs/defrag', { method: 'POST', body: { mount } }),
  btrfsDeviceStats: (mount?: string) => api<{ devices: any[] }>(`/storage/btrfs/device-stats${mount ? `?mount=${mount}` : ''}`),
  btrfsSend: (snapshot: string, output: string) => api<{ success: boolean; message: string }>('/storage/btrfs/send', { method: 'POST', body: { snapshot, output } }),
  btrfsReceive: (input: string, target: string) => api<{ success: boolean; message: string }>('/storage/btrfs/receive', { method: 'POST', body: { input, target } }),
  // FS check & resize
  runFsck: (device: string, fstype?: string, fix?: boolean) => api<{ success: boolean; message: string }>('/storage/fsck', { method: 'POST', body: { device, fstype, fix } }),
  resizeFs: (mount: string, size?: string) => api<{ success: boolean; message: string }>('/storage/resize', { method: 'POST', body: { mount, size } }),
  getFsInfo: (mount?: string) => api<FsInfo>(`/storage/fs-info?mount=${mount || '/'}`),
  // SMART
  getSmart: (device: string) => api<Record<string, any>>(`/storage/smart?device=${encodeURIComponent(device)}`),
  getSmartAll: () => api<{ devices: SmartDevice[] }>('/storage/smart-all'),
  // ZFS
  getZfsStatus: () => api<ZfsStatus>('/storage/zfs'),
  getZfsDatasets: (pool?: string) => api<{ datasets: ZfsDatasetInfo[] }>(`/storage/zfs/datasets${pool ? `?pool=${pool}` : ''}`),
  createZfsDataset: (name: string) => api<{ success: boolean; message: string }>('/storage/zfs/dataset/create', { method: 'POST', body: { name } }),
  destroyZfsDataset: (name: string) => api<{ success: boolean; message: string }>('/storage/zfs/dataset/destroy', { method: 'POST', body: { name } }),
  zfsSnapshot: (dataset: string, snap_name: string) => api<{ success: boolean; message: string }>('/storage/zfs/snapshot', { method: 'POST', body: { dataset, snap_name } }),
  zfsRollback: (dataset: string, snap_name: string) => api<{ success: boolean; message: string }>('/storage/zfs/rollback', { method: 'POST', body: { dataset, snap_name } }),
  // LUKS
  getLuksStatus: () => api<LuksStatus>('/storage/luks'),
  luksOpen: (device: string, name: string, password?: string) => api<{ success: boolean; message: string }>('/storage/luks/open', { method: 'POST', body: { device, name, password } }),
  luksClose: (name: string) => api<{ success: boolean; message: string }>('/storage/luks/close', { method: 'POST', body: { name } }),
  // Benchmark
  runBenchmark: (device: string, test_type?: string, size?: string) => api<{ success: boolean; message: string }>('/storage/benchmark', { method: 'POST', body: { device, test_type, size } }),
  // Block devices
  getDevices: () => api<{ devices: any[] }>('/storage/devices'),
  // Format partition
  formatPartition: (device: string, fstype: string, label?: string) => api<{ success: boolean; message: string }>('/storage/format', { method: 'POST', body: { device, fstype, label } }),
  // SMART self-test
  startSmartTest: (device: string, testType?: string) => api<{ success: boolean; message: string }>('/storage/smart/test', { method: 'POST', body: { device, test_type: testType } }),
  getSmartProgress: (device: string) => api<any>(`/storage/smart/progress?device=${encodeURIComponent(device)}`),
  getSmartTestLog: (device: string) => api<any>(`/storage/smart/test-log?device=${encodeURIComponent(device)}`),
  // Benchmark history
  getBenchmarkHistory: () => api<{ history: any[] }>('/storage/benchmark/history'),
  // IO stats
  getIoStats: () => api<any>('/storage/io-stats'),
}
