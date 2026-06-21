<template>
  <div>
    <FeatureStatus :features="features" />
    <!-- ── Welcome Row ── -->
    <div class="welcome-row">
      <div class="welcome-left">
        <h1 class="welcome-title">概览</h1>
        <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" active-text="30s" title="自动刷新" />
        <span v-if="distro" class="welcome-distro">
          <el-tag size="small" type="info">{{ distro.pretty_name || distro.id }}</el-tag>
        </span>
      </div>
      <div class="welcome-time">{{ nowStr }}</div>
    </div>

    <!-- ── Resource Overview Cards ── -->
    <el-row :gutter="16" class="section-gap">
      <!-- CPU -->
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="resource-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Cpu /></el-icon>
              <span>CPU</span>
              <el-tag v-if="cpuFreq.boost" size="small" type="warning" class="ml-auto">Boost</el-tag>
            </div>
          </template>
          <div v-if="infoLoading" class="panel-state panel-loading"><el-icon class="is-loading"><Loading /></el-icon>加载中...</div>
          <div v-else-if="info" class="resource-body">
            <div class="resource-model" :title="info.cpu">{{ info.cpu }}</div>
            <div class="resource-meta">
              <el-tag size="small">{{ info.cpu_cores }} 核</el-tag>
              <el-tag size="small">{{ info.cpu_threads }} 线程</el-tag>
            </div>
            <!-- Per-core mini bars -->
            <div v-if="cpuFreq.cores?.length" class="cpu-cores-mini">
              <div v-for="c in cpuFreq.cores.slice(0, 16)" :key="c.core" class="core-bar-wrapper">
                <div class="core-bar" :style="{ height: cpuBarHeight(c.cur_khz, c.max_khz), backgroundColor: cpuBarColor(c.cur_khz, c.max_khz) }" :title="`Core ${c.core}: ${c.cur_khz ? (c.cur_khz/1000).toFixed(0) : '—'} / ${c.max_khz ? (c.max_khz/1000).toFixed(0) : '—'} MHz`"></div>
              </div>
            </div>
            <div class="text-xs" style="color: var(--text-2)">
              {{ cpuFreq.governor || '' }} {{ cpuFreq.driver ? '· ' + cpuFreq.driver : '' }}
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 内存 -->
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="resource-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Memo /></el-icon>
              <span>内存</span>
            </div>
          </template>
          <div v-if="infoLoading" class="panel-state panel-loading"><el-icon class="is-loading"><Loading /></el-icon>加载中...</div>
          <div v-else-if="info" class="resource-body">
            <div class="resource-value">
              <span class="resource-used">{{ info.ram_used_gb }}</span>
              <span class="resource-sep"> / </span>
              <span class="resource-total">{{ info.ram_total_gb }} GB</span>
            </div>
            <el-progress
              :percentage="info.ram_percent"
              :color="progressColor(info.ram_percent)"
              :stroke-width="8"
            />
          </div>
        </el-card>
      </el-col>

      <!-- 磁盘 -->
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="resource-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Odometer /></el-icon>
              <span>磁盘</span>
            </div>
          </template>
          <div v-if="infoLoading" class="panel-state panel-loading"><el-icon class="is-loading"><Loading /></el-icon>加载中...</div>
          <div v-else-if="info" class="resource-body">
            <div class="resource-value">
              <span class="resource-used">{{ info.disk_used_gb }}</span>
              <span class="resource-sep"> / </span>
              <span class="resource-total">{{ info.disk_total_gb }} GB</span>
            </div>
            <el-progress
              :percentage="info.disk_percent"
              :color="progressColor(info.disk_percent)"
              :stroke-width="8"
            />
          </div>
        </el-card>
      </el-col>

      <!-- 运行时间 -->
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="resource-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><DataAnalysis /></el-icon>
              <span>运行时间</span>
            </div>
          </template>
          <div v-if="infoLoading" class="panel-state panel-loading"><el-icon class="is-loading"><Loading /></el-icon>加载中...</div>
          <div v-else-if="info" class="resource-body">
            <div class="resource-uptime">{{ info.uptime }}</div>
            <div class="resource-meta">
              <el-tag size="small">内核 {{ info.kernel }}</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ── Quick Actions ── -->
    <el-card shadow="never" class="section-gap">
      <template #header>
        <div class="card-header">
          <el-icon :size="18"><Promotion /></el-icon>
          <span>快捷操作</span>
        </div>
      </template>
      <div class="quick-actions">
        <el-button type="warning" @click="runUpdate" :loading="updateState.running" :icon="Finished">
          系统更新
        </el-button>
        <el-button @click="router.push('/services')" :icon="Setting">
          服务管理
        </el-button>
        <el-button @click="router.push('/packages')" :icon="Box">
          软件包
        </el-button>
        <el-button @click="router.push('/gpu')" :icon="Monitor">
          GPU 管理
        </el-button>
        <el-divider direction="vertical" />
        <el-button v-for="(act, i) in customActions" :key="i" @click="router.push(act.route)" :icon="Promotion">
          {{ act.label }}
          <el-icon class="ml-1" @click.stop="removeCustomAction(i)" style="font-size:10px;opacity:0.5"><Close /></el-icon>
        </el-button>
        <el-button plain size="small" @click="showAddAction = true" :icon="CirclePlus" style="border-style: dashed">
          自定义
        </el-button>
      </div>
      <!-- Update output terminal -->
      <div v-if="updateState.output" class="mt-4">
        <TerminalOutput
          :output-html="updateOutputHtml"
          :running="updateState.running"
          :done="updateState.done"
          :exit-code="updateState.exitCode ?? 0"
          :show-clear="true"
          placeholder="等待输出..."
          @clear="clearUpdate"
          @cancel="stopUpdate"
        />
      </div>
    </el-card>

    <!-- ── Network Traffic + CPU Temp ── -->
    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Connection /></el-icon>
              <span>网络流量</span>
              <span class="card-header-extra">实时 (2s)</span>
            </div>
          </template>
          <div v-if="traffic.interfaces.length" class="traffic-list">
            <div v-for="iface in displayTraffic" :key="iface.name" class="traffic-row">
              <span class="traffic-name font-mono">{{ iface.name }}</span>
              <span class="traffic-rx">↓ {{ iface.rx_rate }}</span>
              <span class="traffic-tx">↑ {{ iface.tx_rate }}</span>
            </div>
          </div>
          <div v-else class="text-xs text-center py-4" style="color: var(--text-2)">获取中...</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Odometer /></el-icon>
              <span>温度 & 风扇</span>
            </div>
          </template>
          <div v-if="thermal.cpu_temp !== null" class="thermal-body">
            <div class="thermal-temp">
              <span class="thermal-label">CPU</span>
              <span class="thermal-value" :style="{color: thermal.cpu_temp > 70 ? 'var(--red)' : thermal.cpu_temp > 50 ? 'var(--yellow)' : 'var(--green)'}">
                {{ thermal.cpu_temp }}°C
              </span>
            </div>
            <div v-for="fan in thermal.fans" :key="fan.name" class="thermal-fan">
              <span class="text-xs" style="color: var(--text-2)">{{ fan.name }}</span>
              <span class="text-xs font-mono">{{ fan.rpm }} RPM</span>
            </div>
          </div>
          <div v-else-if="thermal.loading" class="text-xs text-center py-4" style="color: var(--text-2)">获取中...</div>
          <div v-else class="text-xs text-center py-4" style="color: var(--text-2)">无法获取温度信息</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ── Notifications ── -->
    <el-card v-if="notifications.length" shadow="never" class="section-gap">
      <template #header>
        <div class="card-header">
          <el-icon :size="18"><Warning /></el-icon>
          <span>最近系统事件</span>
          <span class="card-header-extra">journalctl -p 3 -n 3</span>
        </div>
      </template>
      <div v-for="(ev, i) in notifications" :key="i" class="notification-row text-xs font-mono" style="color: var(--text-1); padding: 2px 0">
        {{ ev }}
      </div>
    </el-card>

    <!-- ── Recent Logs Preview ── -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon :size="18"><DataAnalysis /></el-icon>
          <span>最近日志</span>
          <span class="card-header-extra">journalctl -n 20</span>
        </div>
      </template>
      <div v-if="logsLoading" class="panel-state panel-loading"><el-icon class="is-loading"><Loading /></el-icon>加载日志中...</div>
      <div v-else-if="logsError" class="panel-state panel-error">{{ logsError }}</div>
      <div v-else class="terminal dashboard-logs">{{ logs }}</div>
    </el-card>
    <!-- ── Add Custom Action Dialog ── -->
    <el-dialog v-model="showAddAction" title="添加快捷操作" width="380px">
      <el-form label-width="60px" size="small">
        <el-form-item label="名称">
          <el-input v-model="newActionLabel" placeholder="如: 配置编辑" @keyup.enter="addCustomAction" />
        </el-form-item>
        <el-form-item label="路由">
          <el-select v-model="newActionRoute" class="w-full" filterable placeholder="选择页面">
            <el-option label="概览 /" value="/" />
            <el-option label="系统参数 /system" value="/system" />
            <el-option label="网络设置 /network" value="/network" />
            <el-option label="服务管理 /services" value="/services" />
            <el-option label="磁盘管理 /disk" value="/disk" />
            <el-option label="GPU 驱动 /gpu" value="/gpu" />
            <el-option label="软件包 /packages" value="/packages" />
            <el-option label="配置编辑 /config" value="/config" />
            <el-option label="系统救援 /rescue" value="/rescue" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddAction = false">取消</el-button>
        <el-button type="primary" @click="addCustomAction">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { useRouter } from 'vue-router'
import { systemApi } from '@/api/system'
import { networkApi } from '@/api/network'
import { useSseTask } from '@/composables/useSseTask'
import { useToast } from '@/composables/useToast'
import type { SystemInfo, DistroInfo } from '@/types/api'
import TerminalOutput from '@/components/terminal/TerminalOutput.vue'
import {
  Cpu, Memo, Odometer, DataAnalysis, Promotion, Finished, Setting, Box, Monitor, Loading,
  Connection, Warning, CirclePlus, Close,
} from '@element-plus/icons-vue'

const router = useRouter()
const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['init_system','package_manager','sudo'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }

// ── Current time ──
const nowStr = ref('')
let _clockTimer: ReturnType<typeof setInterval> | null = null
function tick() {
  nowStr.value = new Date().toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  })
}

// ── Distro ──
const distro = ref<DistroInfo | null>(null)

// ── System info ──
const info = ref<SystemInfo | null>(null)
const infoLoading = ref(true)

async function loadInfo() {
  try {
    info.value = await systemApi.getInfo()
  } catch (e: any) {
    // Silently fail — cards will just show loading indefinitely
  } finally {
    infoLoading.value = false
  }
}

// ── Progress bar color ──
function progressColor(pct: number): string {
  if (pct >= 90) return 'var(--red)'
  if (pct >= 70) return 'var(--yellow)'
  return 'var(--green)'
}

// ── Update via SSE ──
const { state: updateState, start: startUpdate, stop: stopUpdate, clear: clearUpdate, outputHtml: updateOutputHtml } = useSseTask()

// ── Custom Actions (localStorage persisted) ──
interface CustomAction { label: string; route: string }
const CUSTOM_ACTIONS_KEY = 'tuxtacklebox_custom_actions'
const customActions = ref<CustomAction[]>([])
const showAddAction = ref(false)
const newActionLabel = ref('')
const newActionRoute = ref('/system')

function loadCustomActions() {
  try {
    const raw = localStorage.getItem(CUSTOM_ACTIONS_KEY)
    customActions.value = raw ? JSON.parse(raw) : []
  } catch { customActions.value = [] }
}
function saveCustomActions() {
  localStorage.setItem(CUSTOM_ACTIONS_KEY, JSON.stringify(customActions.value))
}
function addCustomAction() {
  if (!newActionLabel.value.trim() || !newActionRoute.value) return
  customActions.value.push({ label: newActionLabel.value.trim(), route: newActionRoute.value })
  saveCustomActions()
  showAddAction.value = false
  newActionLabel.value = ''
  newActionRoute.value = '/system'
}
function removeCustomAction(index: number) {
  customActions.value.splice(index, 1)
  saveCustomActions()
}

async function runUpdate() {
  try {
    const r = await systemApi.update()
    if (r && r.task_id) {
      startUpdate(r.task_id)
    } else {
      toast.error('无法启动系统更新任务')
    }
  } catch {
    toast.error('启动系统更新失败')
  }
}

// ── Journal logs ──
const logs = ref('')
const logsLoading = ref(true)
const logsError = ref('')

async function loadLogs() {
  try {
    const data = await systemApi.getJournalLogs(20)
    logs.value = data.logs || ''
  } catch (e: any) {
    logsError.value = e?.message || '加载日志失败'
  } finally {
    logsLoading.value = false
  }
}

// ── Network traffic (polled every 2s) ──
const traffic = ref<{ interfaces: any[]; total_rx: number; total_tx: number }>({ interfaces: [], total_rx: 0, total_tx: 0 })
const trafficPrev = ref<Record<string, { rx: number; tx: number; ts: number }>>({})
const displayTraffic = ref<any[]>([])
let _trafficTimer: ReturnType<typeof setInterval> | null = null

function formatRate(bytesPerSec: number): string {
  if (bytesPerSec === 0) return '0 B/s'
  if (bytesPerSec > 1024*1024*1024) return (bytesPerSec/1024/1024/1024).toFixed(2)+' GB/s'
  if (bytesPerSec > 1024*1024) return (bytesPerSec/1024/1024).toFixed(1)+' MB/s'
  if (bytesPerSec > 1024) return (bytesPerSec/1024).toFixed(1)+' KB/s'
  return bytesPerSec.toFixed(0)+' B/s'
}

async function loadTraffic() {
  try {
    const t = await networkApi.getTraffic()
    const now = Date.now()
    const prev = { ...trafficPrev.value }
    const nowSnapshot: Record<string, { rx: number; tx: number; ts: number }> = {}
    const display: any[] = []

    for (const iface of t.interfaces) {
      // Skip loopback and virtual interfaces
      if (iface.name === 'lo' || iface.name.startsWith('docker') ||
          iface.name.startsWith('veth') || iface.name.startsWith('br-') ||
          iface.name.startsWith('virbr') || iface.name.startsWith('tun') ||
          iface.name.startsWith('wg')) continue
      nowSnapshot[iface.name] = { rx: iface.rx_bytes, tx: iface.tx_bytes, ts: now }
      const p = prev[iface.name]
      if (p && p.ts > 0) {
        const elapsed = (now - p.ts) / 1000  // seconds
        if (elapsed > 0) {
          const rxRate = Math.max(0, (iface.rx_bytes - p.rx) / elapsed)
          const txRate = Math.max(0, (iface.tx_bytes - p.tx) / elapsed)
          display.push({
            name: iface.name,
            rx_rate: formatRate(rxRate),
            tx_rate: formatRate(txRate),
          })
        }
      } else {
        // First data point — show placeholder
        display.push({ name: iface.name, rx_rate: '—', tx_rate: '—' })
      }
    }
    trafficPrev.value = nowSnapshot
    displayTraffic.value = display
    traffic.value = t
  } catch {}
}

// ── Thermal ──
const thermal = ref<{ cpu_temp: number | null; fans: any[]; loading: boolean }>({ cpu_temp: null, fans: [], loading: true })
async function loadThermal() {
  try {
    const t = await systemApi.getThermal()
    thermal.value = { cpu_temp: t.cpu_temp, fans: t.fans || [], loading: false }
  } catch { thermal.value.loading = false }
}

// ── CPU 频率 ──
const cpuFreq = ref<any>({ cores: [], governor: '', driver: '', boost: false })
async function loadCpuFreq() { try { cpuFreq.value = await systemApi.getCpuFreq() } catch {} }
function cpuBarHeight(cur: number | null, max: number | null): string {
  if (!cur || !max || max <= 0) return '4px'
  const pct = Math.min(cur / max, 1)
  return (4 + pct * 28) + 'px'
}
function cpuBarColor(cur: number | null, max: number | null): string {
  if (!cur || !max) return 'var(--border)'
  const pct = cur / max
  if (pct > 0.9) return 'var(--red)'
  if (pct > 0.6) return 'var(--yellow)'
  return 'var(--green)'
}

// ── Notifications ──
const notifications = ref<string[]>([])
async function loadNotifications() {
  try {
    const n = await systemApi.getNotifications()
    notifications.value = n.events || []
  } catch {}
}

// Auto-refresh (30s)
const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(() => { loadInfo(); loadThermal(); loadNotifications(); loadCpuFreq() }, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}

// ── Lifecycle ──
onMounted(async () => { fetchFeatures();
  tick()
  _clockTimer = setInterval(tick, 1000)
  _trafficTimer = setInterval(loadTraffic, 2000)

  // Load distro in parallel
  systemApi.getDistro().then(d => { distro.value = d }).catch(() => {})

  loadCustomActions()
  await Promise.all([loadInfo(), loadLogs(), loadTraffic(), loadThermal(), loadNotifications(), loadCpuFreq()])
})

onBeforeUnmount(() => {
  if (_clockTimer) { clearInterval(_clockTimer); _clockTimer = null }
  if (_trafficTimer) { clearInterval(_trafficTimer); _trafficTimer = null }
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null }
  stopUpdate()
})
</script>

<style scoped>
/* ── Welcome Row ── */
.welcome-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32px;
  flex-wrap: wrap;
  gap: 16px;
}
.welcome-left {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}
.welcome-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-0);
  letter-spacing: -0.3px;
  margin: 0;
}
.welcome-distro {
  display: flex;
  align-items: center;
}
.welcome-time {
  font-size: 15px;
  color: var(--text-1);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

/* ── Resource Cards ── */
.resource-card {
  height: 100%;
}
.resource-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 90px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: var(--text-0);
}
.card-header .el-icon {
  color: var(--accent);
}
.card-header-extra {
  margin-left: auto;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-2);
  font-family: 'JetBrains Mono', monospace;
}
.resource-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.resource-model {
  font-size: 14px;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.resource-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.resource-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-0);
}
.resource-used {
  color: var(--accent);
}
.resource-sep {
  color: var(--text-2);
  font-weight: 400;
}
.resource-total {
  font-weight: 500;
}
.resource-uptime {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-0);
}

/* ── Quick Actions ── */
.quick-actions {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

/* ── Dashboard logs ── */
.dashboard-logs {
  min-height: 180px;
  max-height: 360px;
}

/* ── Traffic ── */
.traffic-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.traffic-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}
.traffic-row:last-child { border-bottom: none; }
.traffic-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-0);
  min-width: 60px;
}
.traffic-rx {
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--green);
}
.traffic-tx {
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--accent);
}

/* ── Thermal ── */
.thermal-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.thermal-temp {
  display: flex;
  align-items: center;
  gap: 14px;
}
.thermal-label {
  font-size: 14px;
  color: var(--text-1);
}
.thermal-value {
  font-size: 26px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}
.thermal-fan {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ── Notifications ── */
.notification-row {
  padding: 6px 10px !important;
  border-left: 3px solid var(--yellow);
  margin-bottom: 6px;
  background: var(--bg-0);
  border-radius: 4px;
  font-size: 13px;
}

/* ── CPU cores mini bars ── */
.cpu-cores-mini {
  display: flex;
  gap: 3px;
  align-items: flex-end;
  height: 40px;
  padding: 3px 0;
}
.core-bar-wrapper {
  flex: 1;
  display: flex;
  align-items: flex-end;
  height: 100%;
}
.core-bar {
  width: 100%;
  min-height: 4px;
  border-radius: 2px 2px 0 0;
  transition: height 0.5s ease, background-color 0.5s ease;
}

.font-mono { font-family: 'JetBrains Mono', monospace; }

.section-gap { margin-bottom: 20px; }

</style>
