// ── Generic API wrapper ──

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

// ── System ──

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

export interface DistroInfo {
  id: string
  like: string
  pkg_manager: string
  version: string
  pretty_name: string
  is_kylin: boolean
  kylin_edition: string
}

export interface SshConfig {
  port: string
  permit_root_login: string
  password_auth: string
  pubkey_auth: string
}

export interface SwapInfo {
  total: string
  used: string
  free: string
  files: Array<{ path: string; type: string; size_kb: string; used_kb: string }>
}

export interface NtpStatus {
  ntp_enabled: boolean
  synced: boolean
  service?: string
}

export interface UlimitsInfo {
  file: string
  running: string
}

export interface KernelModule {
  name: string
  size: string
  used_by: number
  used_by_list: string
}

export interface KernelModulesResponse {
  modules: KernelModule[]
}

export interface UserInfo {
  username: string
  uid: number
  gid: number
  home: string
  shell: string
}

export interface UsersResponse {
  users: UserInfo[]
}

// ── System optimization ──

export interface ServiceOptimizeItem {
  name: string
  desc: string
  safe: boolean
  enabled: boolean
  active: boolean
}

export interface ServiceOptimizeResponse {
  services: ServiceOptimizeItem[]
}

export interface ServiceOptimizeResult {
  results: Array<{ name: string; success: boolean }>
}

export interface QuickKernelParam {
  key: string
  current: string
  desc: string
  recommended: string
  type: string
}

export interface QuickParamsResponse {
  params: QuickKernelParam[]
}

export interface OptimizationProfileSummary {
  label: string
  desc: string
}

export interface OptimizationProfileList {
  profiles: Record<string, OptimizationProfileSummary>
}

export interface SysctlChange {
  key: string
  current: string
  recommended: string
  will_change: boolean
}

export interface SvcChange {
  name: string
  enabled: boolean
  active: boolean
  will_disable: boolean
}

export interface OptimizationPreview {
  success: boolean
  profile: string
  label: string
  desc: string
  sysctl_changes: SysctlChange[]
  svc_changes: SvcChange[]
}

export interface SysctlResult {
  key: string
  success: boolean
  message: string
}

export interface SvcResult {
  name: string
  success: boolean
}

export interface OptimizationApplyResult {
  success: boolean
  profile: string
  sysctl_results: SysctlResult[]
  svc_results: SvcResult[]
}

// ── Boot & kernel ──

export interface GrubEntry {
  index: number
  title: string
  file?: string
}

export interface GrubConfig {
  default: string
  timeout: string
  cmdline: string
  entries: GrubEntry[]
  config_file: string
  grub_cfg_path: string
  mkconfig_cmd: string
  bootloader?: string  // 'grub' | 'systemd-boot' | 'unknown'
}

export interface CmdlinePreset {
  label: string
  params: string
  desc: string
}

export interface CmdlinePresetsResponse {
  presets: Record<string, CmdlinePreset>
}

export interface CpuGovernorInfo {
  available: string[]
  current: string
  driver: string
}

export interface IoSchedulerDevice {
  name: string
  current: string
  available: string[]
}

export interface IoSchedulerInfo {
  devices: IoSchedulerDevice[]
}

export interface MacStatus {
  selinux?: { enabled: boolean; mode: string; config_mode: string }
  apparmor?: { enabled: boolean; mode: string }
  type: string
}

// ── Network ──

export interface NetworkInterface {
  name: string
  ipv4: string[]
  ipv6: string[]
  mac: string
  is_up: boolean
  speed: number
  mtu?: number
}

export interface PortInfo {
  protocol: string
  local_address: string
  process: string
}

export interface FirewallToolStatus {
  installed: boolean
  active: boolean
  status: string
}

export interface FirewallStatus {
  active: string | null
  installed: string[]
  ufw: FirewallToolStatus & { default_policy: string }
  firewalld: FirewallToolStatus & { zones: string[] }
  nftables: FirewallToolStatus & { rules_count: number }
  iptables: FirewallToolStatus & { rules_count: number }
}

export interface BondInfo {
  name: string
  slaves: string[]
  mode: string
  status: string
}

export interface BondsResponse {
  bonds: BondInfo[]
  slaves: string[]
  modes: Record<string, string>
}

export interface BondOptionDef {
  desc: string
  default: string
  values: string[]
}

export interface VlanInfo {
  name: string
  id: string
  parent: string
  protocol: string
}

export interface BridgeInfo {
  name: string
  members: string[]
  up: boolean
}

export interface RouteInfo {
  dst: string
  gateway: string
  dev: string
  proto: string
  metric: string
}

export interface WireGuardInfo {
  name: string
  up: boolean
  port?: string
  peers?: string[]
}

export interface WireGuardCheckResult {
  available: boolean
  message: string
}

// ── Storage (LVM / Btrfs / ZFS / LUKS / SMART) ──

export interface PvInfo {
  name: string
  size: string
  vg: string
  free: string
}

export interface VgInfo {
  name: string
  size: string
  free: string
  pv_count: number
  lv_count: number
}

export interface LvInfo {
  name: string
  vg: string
  size: string
  pool?: string
  data_percent?: string
  attr?: string
}

export interface LvmStatus {
  installed?: boolean
  pvs: PvInfo[]
  vgs: VgInfo[]
  lvs: LvInfo[]
}

export interface BtrfsSubvolume {
  id: string
  gen?: string
  path: string
  is_default?: boolean
}

export interface BtrfsDevice {
  path: string
  size: string
}

export interface BtrfsFilesystem {
  label: string
  devices: BtrfsDevice[]
  uuid: string
}

export interface BtrfsStatus {
  installed?: boolean
  filesystems: BtrfsFilesystem[]
  subvolumes: BtrfsSubvolume[]
}

export interface ZfsPoolInfo {
  name: string
  size: string
  allocated: string
  free: string
  health: string
}

export interface ZfsDatasetInfo {
  name: string
  used: string
  available: string
  mountpoint: string
}

export interface ZfsStatus {
  installed?: boolean
  pools: ZfsPoolInfo[]
}

export interface LuksDeviceInfo {
  name: string
  size: string
  parent: string
  mountpoint: string
}

export interface LuksStatus {
  installed: boolean
  devices: LuksDeviceInfo[]
}

export interface SmartDevice {
  device: string
  health: string
  temperature: string | number
  power_on_hours?: number | string
  reallocated_sectors?: number | string
}

export interface FsInfo extends Record<string, string> {
  device: string
  type: string
  size: string
  used: string
  available: string
  mount: string
}

export interface RaidArray {
  name: string
  level: string
  state: string
  devices: string[]
  size?: string
}

export interface StorageDevicesResponse {
  devices: BlockDevice[]
}

// ── GPU ──

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

export interface OfflinePackage {
  name: string
  path: string
  extract_dir?: string
  meta: Record<string, any>
  package_count: number
  has_install_script: boolean
  size?: number
}

// ── Disk ──

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

export interface DiskUsageDevice {
  source: string
  size_bytes: number
  used_bytes: number
  avail_bytes: number
  use_pct: string
  target: string
}

// ── Packages ──

export interface SoftwareItem {
  [key: string]: {
    desc: string
    icon: string
    [pkgManager: string]: string
  }
}

export interface InstalledPackage {
  name: string
  version: string
  status: string
  arch: string
  source?: string  // 'native' | 'snap' | 'flatpak'
  publisher?: string
  app_id?: string
}

export interface InstalledPackagesResponse {
  packages: InstalledPackage[]
}

export interface RepoItem {
  name?: string
  line?: string
  file?: string
  baseurl?: string
  enabled?: string
}

export interface ReposResponse {
  manager: string
  repos: RepoItem[]
  files: string[]
}

export interface UpdateHistoryItem {
  time: string
  action: string
  packages: string
  result: string
}

export interface SoftwareCatalog {
  [category: string]: {
    [pkgName: string]: {
      desc: string
      icon: string
      [pkgManager: string]: string
    }
  }
}

export interface SearchPackageResult {
  name: string
  version?: string
  description?: string
  repo?: string
}

export interface GenPackage {
  package: string
  version?: string
  description: string
}

// ── Rescue ──

export interface IsoItem {
  source: string
  target: string
  fstype: string
  size?: number
  name?: string
  mount_point?: string
  iso_path?: string
  host?: string
  remote_path?: string
  user?: string
  is_mounted?: boolean
}

export interface RepoStatus {
  configured: boolean
  config_file: string
  pkg_manager: string
}

export interface ChrootStatus {
  root: string
  mounts: Record<string, boolean>
  all_ready: boolean
}

export interface FileItem {
  size: number
  name: string
}

// ── Config ──

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

// ── Services ──

export interface ServiceInfo {
  name: string
  load: string
  active: string
  sub: string
  description: string
}

// ── Dashboard ──

export interface NetworkTraffic {
  interfaces: NetworkTrafficInterface[]
  total_rx: number
  total_tx: number
}

export interface NetworkTrafficInterface {
  name: string
  rx_bytes: number
  tx_bytes: number
}

export interface ThermalInfo {
  cpu_temp: number | null
  fans: FanInfo[]
}

export interface FanInfo {
  name: string
  rpm: number
}

export interface NotificationsResponse {
  events: string[]
}

// ── Packages ──

export interface RepoRawResponse {
  manager: string
  files: Record<string, string>
}

// ── Storage ──

export interface BtrfsDeviceStats {
  devices: BtrfsDeviceStat[]
}

export interface BtrfsDeviceStat {
  device: string
  stats: string
}
