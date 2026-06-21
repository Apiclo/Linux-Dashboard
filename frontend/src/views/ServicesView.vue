<template>
  <div>
    <div class="page-title"><el-icon><Lightning /></el-icon>服务管理
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新" />
    </div>

    <FeatureStatus :features="features" />

    <!-- 搜索与操作 -->
    <el-card shadow="never" class="mb-6">
      <div class="flex flex-wrap items-center gap-4 mb-4">
        <el-input v-model="searchRaw" placeholder="搜索服务..." size="small" class="w-52" />
        <el-select v-model="filterRaw" placeholder="状态" size="small" class="w-32" clearable>
          <el-option v-for="opt in filterOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-button size="small" plain @click="load"><el-icon><Refresh /></el-icon></el-button>
      </div>

      <el-divider content-position="left" class="!my-4">运行控制</el-divider>
      <div class="flex flex-wrap gap-4 mb-5 items-center">
        <el-button type="success" size="small" :disabled="!selected" @click="doAction('start')">
          <el-icon><VideoPlay /></el-icon>启动
        </el-button>
        <el-button type="danger" size="small" :disabled="!selected" @click="doAction('stop')">
          <el-icon><VideoPause /></el-icon>停止
        </el-button>
        <el-button type="warning" size="small" :disabled="!selected" @click="doAction('restart')">
          <el-icon><Refresh /></el-icon>重启
        </el-button>
        <span v-if="!selected" class="text-xs ml-auto" style="color: var(--text-2)">请先点击服务行选择 →</span>
      </div>

      <el-divider content-position="left" class="!my-4">开机控制</el-divider>
      <div class="flex flex-wrap gap-4 mb-5">
        <el-button type="success" plain size="small" :disabled="!selected" @click="doAction('enable')">
          <el-icon><CircleCheck /></el-icon>启用
        </el-button>
        <el-button type="danger" plain size="small" :disabled="!selected" @click="doAction('disable')">
          <el-icon><CircleClose /></el-icon>禁用
        </el-button>
        <el-button type="info" plain size="small" class="ml-auto" :disabled="!selected" @click="viewLogs">
          <el-icon><Document /></el-icon>日志
        </el-button>
      </div>
    </el-card>

    <!-- 服务列表 -->
    <el-card shadow="never" class="mb-6" v-loading="loading">
      <div v-if="error" class="panel-error">{{ error }}</div>
      <el-table v-else-if="filtered.length" :data="sortedServices" stripe border size="small" max-height="500" highlight-current-row row-key="name" @row-click="onRowSelect" @sort-change="onServiceSort">
        <el-table-column prop="name" label="服务" min-width="200" sortable="custom">
          <template #default="{ row }"><span class="font-mono text-sm">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column prop="active" label="活跃" width="100" sortable="custom">
          <template #default="{ row }"><el-tag :type="row.active?.startsWith('active') ? 'success' : row.active?.startsWith('failed') ? 'danger' : 'info'">{{ row.active }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="sub" label="子状态" width="100">
          <template #default="{ row }">
            <el-tag :type="subTagType(row.sub)" size="small" effect="dark">{{ row.sub }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
      </el-table>
      <el-empty v-else description="无匹配的服务" :image-size="60" />
    </el-card>

    <!-- 服务详情 -->
    <el-card v-if="selected" shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-2 font-semibold"><el-icon><InfoFilled /></el-icon>{{ selected }} 详情</span>
          <el-button size="small" plain @click="loadServiceDetail">刷新</el-button>
        </div>
      </template>
      <div v-if="svcDetail" class="grid grid-cols-12 gap-5 text-sm">
        <div class="col-span-12 md:col-span-6">
          <div class="mb-3"><strong>状态:</strong> {{ svcDetail.active }} ({{ svcDetail.sub }})</div>
          <div class="mb-3"><strong>PID:</strong> {{ svcDetail.pid || '—' }}</div>
          <div class="mb-3"><strong>内存:</strong> {{ svcDetail.rss_kb ? (svcDetail.rss_kb/1024).toFixed(1)+' MB' : '—' }}</div>
          <div class="mb-3"><strong>CPU:</strong> {{ svcDetail.cpu_percent ? svcDetail.cpu_percent.toFixed(1)+'%' : '—' }}</div>
          <div class="mb-3"><strong>启动:</strong> {{ svcDetail.enabled_status || '—' }}</div>
        </div>
        <div class="col-span-12 md:col-span-6">
          <div class="mb-3"><strong>运行时间:</strong> {{ svcDetail.elapsed || '—' }}</div>
          <div class="mb-3"><strong>监听端口:</strong>
            <span v-if="svcDetail.listen_ports?.length">{{ svcDetail.listen_ports.join(', ') }}</span>
            <span v-else>—</span>
          </div>
          <div class="mb-3">
            <el-button size="small" text type="primary" @click="showDeps = !showDeps">依赖关系 {{ showDeps ? '▲' : '▼' }}</el-button>
          </div>
        </div>
      </div>
      <!-- 依赖树 -->
      <div v-if="showDeps && svcDeps" class="mt-4 p-4 rounded" style="background: var(--bg-0)">
        <div class="text-xs font-semibold mb-1">Requires:</div>
        <div class="flex flex-wrap gap-1 mb-2">
          <el-tag v-for="r in svcDeps.requires" :key="r" size="small" type="warning">{{ r }}</el-tag>
          <span v-if="!svcDeps.requires?.length" style="color: var(--text-2)">无</span>
        </div>
        <div class="text-xs font-semibold mb-1">WantedBy:</div>
        <div class="flex flex-wrap gap-1 mb-2">
          <el-tag v-for="r in svcDeps.wanted_by" :key="r" size="small" type="success">{{ r }}</el-tag>
          <span v-if="!svcDeps.wanted_by?.length" style="color: var(--text-2)">无</span>
        </div>
        <div class="text-xs font-semibold mb-1">Conflicts:</div>
        <div class="flex flex-wrap gap-1">
          <el-tag v-for="r in svcDeps.conflicts" :key="r" size="small" type="danger">{{ r }}</el-tag>
          <span v-if="!svcDeps.conflicts?.length" style="color: var(--text-2)">无</span>
        </div>
      </div>
      <!-- Unit 文件 -->
      <div v-if="svcUnit" class="mt-4">
        <el-button size="small" text @click="showUnit = !showUnit">Unit 文件 {{ showUnit ? '▲' : '▼' }}</el-button>
        <pre v-if="showUnit" class="mt-2 p-3 text-xs font-mono rounded" style="background: var(--bg-1); max-height: 300px; overflow: auto; white-space: pre-wrap">{{ svcUnit.content || '(空)' }}</pre>
      </div>
    </el-card>

    <!-- 日志 -->
    <TerminalOutput
      :output-html="logsHtml"
      :placeholder="selected ? '点击刷新获取日志' : '选择服务后点击查看日志'"
      :running="false"
      :done="!!logs"
      :show-clear="false"
    >
      <template #toolbar-extra>
        <span class="text-xs mr-2" style="color: var(--text-2)">{{ selected ? selected : '' }}</span>
        <el-select v-model="logLines" size="small" class="w-24" @change="selected && viewLogs()">
          <el-option :value="50" label="50 行" />
          <el-option :value="100" label="100 行" />
          <el-option :value="200" label="200 行" />
          <el-option :value="500" label="500 行" />
        </el-select>
        <el-button size="small" plain @click="viewLogs" :disabled="!selected"><el-icon><Refresh /></el-icon></el-button>
      </template>
    </TerminalOutput>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { systemApi } from '@/api/system'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { Refresh, VideoPlay, VideoPause, CircleCheck, CircleClose, InfoFilled } from '@element-plus/icons-vue'
import { servicesApi } from '@/api/services'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useDebounce } from '@/composables/useDebounce'
import TerminalOutput from '@/components/terminal/TerminalOutput.vue'
import type { ServiceInfo } from '@/types/api'

const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['init_system','sudo'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }
const { confirm: showConfirm } = useConfirm()
const loading = ref(false)
const error = ref('')
const services = ref<ServiceInfo[]>([])
const searchRaw = ref('')
const search = useDebounce(searchRaw, 300)
const filterRaw = ref('')
const filter = useDebounce(filterRaw, 300)
const selected = ref('')
const logsHtml = ref('')
const logLines = ref(150)
const serviceSortKey = ref('')
const serviceSortOrder = ref<'ascending' | 'descending' | null>(null)

const filterOptions = [
  { label: 'active', value: 'active' },
  { label: 'failed', value: 'failed' },
  { label: 'inactive', value: 'inactive' },
]

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  const f = filter.value
  return services.value.filter(s =>
    (s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)) && (!f || s.active?.startsWith(f))
  )
})

const sortedServices = computed(() => {
  const arr = [...filtered.value]
  if (serviceSortKey.value && serviceSortOrder.value) {
    arr.sort((a, b) => {
      const va = (a as any)[serviceSortKey.value] ?? ''
      const vb = (b as any)[serviceSortKey.value] ?? ''
      if (va < vb) return serviceSortOrder.value === 'ascending' ? -1 : 1
      if (va > vb) return serviceSortOrder.value === 'ascending' ? 1 : -1
      return 0
    })
  }
  return arr
})

function onServiceSort({ prop, order }: { prop: string; order: string }) {
  serviceSortKey.value = prop
  serviceSortOrder.value = order as 'ascending' | 'descending' | null
}

function subTagType(sub: string): 'success'|'danger'|'warning'|'info' {
  if (!sub) return 'info'
  const s = sub.toLowerCase()
  if (s.includes('running') || s.includes('active')) return 'success'
  if (s.includes('exited') || s.includes('failed')) return 'danger'
  if (s.includes('dead') || s.includes('inactive')) return 'warning'
  return 'info'
}

function onRowSelect(row: ServiceInfo) {
  selected.value = row.name
  loadServiceDetail()
}

async function load() {
  loading.value = true
  error.value = ''
  try { services.value = await servicesApi.getServices() } catch { error.value = '服务列表加载失败，请重试' }
  finally { loading.value = false }
}

async function doAction(action: string) {
  if (!selected.value) return toast.warning('请先选择服务')
  const labels: Record<string, string> = { start: '启动', stop: '停止', restart: '重启', enable: '启用', disable: '禁用' }
  const ok = await showConfirm(`${labels[action]}服务`, `确定${labels[action]}服务 ${selected.value}？`)
  if (!ok) return
  try {
    const res = await servicesApi.action(selected.value, action)
    toast.show(res.message || (res.success ? '已执行' : '失败'), res.success ? 'success' : 'error')
    if (res.success) load()
  } catch { toast.error('操作失败') }
}

async function viewLogs() {
  if (!selected.value) return toast.warning('请先选择服务')
  try { const r = await servicesApi.getLogs(selected.value, logLines.value); logsHtml.value = (r.logs || '无日志').replace(/\n/g, '<br>') } catch { logsHtml.value = '获取失败' }
}

// ── 服务详情 ──
const svcDetail = ref<any>(null)
const svcDeps = ref<any>(null)
const svcUnit = ref<any>(null)
const showDeps = ref(false)
const showUnit = ref(false)

async function loadServiceDetail() {
  if (!selected.value) return
  svcDetail.value = null; svcDeps.value = null; svcUnit.value = null
  try {
    const [detail, deps, unit] = await Promise.all([
      servicesApi.getStatusDetail(selected.value),
      servicesApi.getDependencies(selected.value),
      servicesApi.getUnitFile(selected.value),
    ])
    svcDetail.value = detail
    svcDeps.value = deps
    svcUnit.value = unit
  } catch { /* non-critical */ }
}

const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(load, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}
onMounted(() => { load(); fetchFeatures() })
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
:deep(.el-table__body tr) { cursor: pointer; }
:deep(.el-table__body tr:hover) { background: var(--bg-1) !important; }
</style>
