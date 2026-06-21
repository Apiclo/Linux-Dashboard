export interface ApiResponse<T = any> {
  success: boolean
  message?: string
  data?: T
}

export interface TaskResponse {
  task_id: string
  success?: boolean
  message?: string
}

export interface SystemInfo {
  hostname: string
  os_name: string
  kernel: string
  arch: string
  cpu: string
  cpu_cores: number
  cpu_threads: number
  ram_total_gb: number
  ram_used_gb: number
  ram_percent: number
  disk_total_gb: number
  disk_used_gb: number
  disk_percent: number
  uptime: string
  desktop: string
  shell: string
  timezone: string
  locale: string
}

export interface NetworkInterface {
  name: string
  ipv4: string[]
  ipv6: string[]
  mac: string
  is_up: boolean
  speed: number
}

export interface PortInfo {
  protocol: string
  local_address: string
  process: string
}

export interface ServiceInfo {
  name: string
  load: string
  /** Compound status from systemd, e.g. "active (running)", "failed (Result: exit-code)", "inactive (dead)".
   *  Use startsWith() for comparison, never ===. */
  active: string
  sub: string
  description: string
}

export interface UserInfo {
  username: string
  uid: number
  gid: number
  home: string
  shell: string
}

export interface GpuInfo {
  vendor: string
  type: string
  name: string
  pci_id?: string
  device_id?: string
}

export interface NvidiaSmiInfo {
  index: string
  driver_version: string
  gpu_name: string
  temperature: string
  vram_total: string
  vram_used: string
  utilization: string
  pci_bus: string
}

export interface DistroInfo {
  id: string
  like: string
  pkg_manager: string
  version: string
  pretty_name: string
  is_kylin: boolean
  kylin_edition: string
}

export interface SecureBootInfo {
  enabled: boolean
  output: string
}

export interface NouveauInfo {
  loaded: boolean
  blacklisted: boolean
}

export interface GpuDetectData {
  gpus: GpuInfo[]
  nvidia_info: NvidiaSmiInfo | null
  nvidia_gpus: NvidiaSmiInfo[]
  nvidia_detail: Record<string, string>
  nouveau: NouveauInfo
  display_manager: string | null
  kernel: string
  kernel_headers: string
  cuda_info: string
  secure_boot: SecureBootInfo
  distro: DistroInfo
  aur_helper: string | null
  loaded_modules: string
  modprobe_configs: Record<string, string>
}

export interface NvidiaVersion {
  package: string
  version: string
  description: string
  source: string
}

export interface OfflinePackage {
  name: string
  path: string
  extract_dir?: string
  meta: Record<string, any>
  package_count: number
  has_install_script: boolean
  size?: number
}

export interface CompatCheck {
  name: string
  status: string
  detail: string
}

export interface CompatResult {
  checks: CompatCheck[]
  warnings: CompatCheck[]
  errors: CompatCheck[]
}

export interface BlockDevice {
  name: string
  size: string
  type: string
  mountpoint: string
  fstype: string
  model: string
  uuid: string
  children: BlockDevice[]
}

export interface SoftwareItem {
  [key: string]: {
    desc: string
    icon: string
    [pkgManager: string]: string
  }
}

export interface GenPackage {
  package: string
  version?: string
  description: string
}

export interface ConfigKey {
  key: string
  desc: string
  type?: 'bool' | 'number' | 'text'
  true_val?: string
  false_val?: string
}

export interface ConfigPreset {
  path: string
  keys: ConfigKey[]
}
