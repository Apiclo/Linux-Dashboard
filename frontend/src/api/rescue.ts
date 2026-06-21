import { api } from './request'
import type { IsoItem, RepoStatus, ChrootStatus, FileItem } from '@/types/api'

export const rescueApi = {
  // ── ISO management ──
  mountIso: (iso_path: string, mount_point: string, configure_repo: boolean) =>
    api<{ success: boolean; message?: string; repo_configured?: boolean; distro_family?: string }>(
      '/rescue/iso/mount', { method: 'POST', body: { iso_path, mount_point, configure_repo } }),

  umountIso: (mount_point: string) =>
    api<{ success: boolean; message: string }>('/rescue/iso/umount', { method: 'POST', body: { mount_point } }),

  getMountedIsos: () =>
    api<{ isos: IsoItem[] }>('/rescue/iso/mounted'),

  listIsoContent: (iso_path: string) =>
    api<{ success: boolean; items: FileItem[]; message: string }>('/rescue/iso/list', { method: 'POST', body: { iso_path } }),

  getRepoStatus: () =>
    api<RepoStatus>('/rescue/iso/repo-status'),

  removeLocalRepo: () =>
    api<{ success: boolean; message: string }>('/rescue/iso/remove-repo', { method: 'POST' }),

  // ── SFTP ──
  checkSshfs: () =>
    api<{ available: boolean; message: string }>('/rescue/sftp/check'),

  mountSftp: (user: string, host: string, port: number, remote_path: string, mount_point: string, options: string) =>
    api<{ success: boolean; message: string }>('/rescue/sftp/mount', {
      method: 'POST', body: { user, host, port, remote_path, mount_point, options },
    }),

  umountSftp: (mount_point: string) =>
    api<{ success: boolean; message: string }>('/rescue/sftp/umount', { method: 'POST', body: { mount_point } }),

  getSftpMounts: () =>
    api<{ mounts: IsoItem[] }>('/rescue/sftp/mounted'),

  // ── Chroot ──
  prepareChroot: (root: string) =>
    api<{ success: boolean; message: string }>('/rescue/chroot/prepare', { method: 'POST', body: { root } }),

  teardownChroot: (root: string) =>
    api<{ success: boolean; message: string }>('/rescue/chroot/teardown', { method: 'POST', body: { root } }),

  getChrootStatus: (root: string) =>
    api<ChrootStatus>(`/rescue/chroot/status?root=${encodeURIComponent(root)}`),

  // ── File browser ──
  listDirectory: (path: string) =>
    api<{ success: boolean; items: any[]; path: string }>('/rescue/browse?path=' + encodeURIComponent(path)),

  // ── System (grub + initramfs) ──
  grubRepair: (disk: string, root: string) =>
    api<{ success: boolean; message: string }>('/system/grub-repair', { method: 'POST', body: { disk, root } }),

  rebuildInitramfs: (all: boolean) =>
    api<{ task_id: string }>('/system/initramfs-rebuild', { method: 'POST', body: { all } }),

  // ── System backup ──
  createBackup: (name?: string, includeHome?: boolean) =>
    api<{ success: boolean; name: string; path: string; file_count: number; errors: string[] }>(
      '/rescue/backup/create', { method: 'POST', body: { name, include_home: includeHome } }),
  listBackups: () => api<{ snapshots: any[] }>('/rescue/backup/list'),
  deleteBackup: (name: string) => api<{ success: boolean; message: string }>(
    '/rescue/backup/delete', { method: 'POST', body: { name } }),
  restoreBackupFile: (snapshot: string, filename: string) => api<{ success: boolean; message: string }>(
    '/rescue/backup/restore', { method: 'POST', body: { snapshot, filename } }),
  compareBackup: (name: string) => api<{ diffs: any[] }>(`/rescue/backup/compare?name=${encodeURIComponent(name)}`),
}
