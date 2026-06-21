<template>
  <div>
    <div class="page-title">
      <el-icon><Monitor /></el-icon>进程管理
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新 (30s)" />
    </div>

    <FeatureStatus :features="features" />

    <!-- Controls -->
    <el-card shadow="never" class="mb-6">
      <div class="flex gap-4 mb-4 items-center flex-wrap">
        <el-input v-model="procFilter" placeholder="进程名过滤..." size="small" class="w-52" @keyup.enter="loadProcesses" />
        <el-select v-model="procSort" size="small" class="w-28" @change="loadProcesses">
          <el-option label="CPU" value="cpu" /><el-option label="内存" value="mem" /><el-option label="PID" value="pid" />
        </el-select>
        <el-button size="small" @click="loadProcesses">刷新</el-button>
        <el-button size="small" plain @click="loadProcTree = !loadProcTree">{{ loadProcTree ? '列表视图' : '进程树' }}</el-button>
        <span class="text-sm ml-auto" style="color: var(--text-2)">
          Load: {{ sysLoad.load_avg?.[0]?.toFixed(1) || '—' }} {{ sysLoad.load_avg?.[1]?.toFixed(1) || '—' }} {{ sysLoad.load_avg?.[2]?.toFixed(1) || '—' }}
        </span>
      </div>

      <!-- Process List -->
      <el-table v-if="!loadProcTree && procs.length" :data="procs" size="small" stripe border max-height="500">
        <el-table-column prop="pid" label="PID" width="80" />
        <el-table-column prop="user" label="用户" width="100" />
        <el-table-column prop="cpu" label="CPU%" width="80">
          <template #default="{ row }">
            <span :style="{ color: row.cpu > 50 ? 'var(--red)' : row.cpu > 20 ? 'var(--yellow)' : 'var(--text-1)' }">{{ row.cpu }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="mem" label="MEM%" width="80" />
        <el-table-column prop="command" label="命令" min-width="250" show-overflow-tooltip>
          <template #default="{ row }"><span class="font-mono text-sm">{{ row.command }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="showProcDetail(row.pid)">详情</el-button>
            <el-popconfirm title="确定终止此进程？" @confirm="doKill(row.pid, 'SIGTERM')">
              <template #reference><el-button size="small" text type="danger">终止</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- Process Tree / Detail -->
      <div v-if="loadProcTree" class="terminal" style="min-height: 250px; max-height: 500px; font-size: 12px" v-html="procTreeHtml"></div>

      <el-empty v-if="!loadProcTree && !procs.length" description="无匹配的进程" :image-size="60" />
    </el-card>

    <!-- Top Processes -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="flex items-center gap-3 font-semibold"><el-icon><DataAnalysis /></el-icon>资源占用 TOP 8</span>
          <el-button size="small" plain @click="loadProcInfo">刷新</el-button>
        </div>
      </template>
      <el-table :data="topProcs" size="small" stripe border>
        <el-table-column prop="pid" label="PID" width="80" />
        <el-table-column prop="cpu" label="CPU%" width="80">
          <template #default="{ row }"><span :style="{ color: row.cpu > 50 ? 'var(--red)' : row.cpu > 20 ? 'var(--yellow)' : 'var(--accent)' }">{{ row.cpu.toFixed(1) }}</span></template>
        </el-table-column>
        <el-table-column prop="mem" label="MEM%" width="80" />
        <el-table-column prop="command" label="命令" min-width="300" show-overflow-tooltip>
          <template #default="{ row }"><span class="font-mono text-sm">{{ row.command }}</span></template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!topProcs.length" description="加载中..." :image-size="40" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { Monitor, DataAnalysis } from '@element-plus/icons-vue'

const toast = useToast()

// Features
const features = ref<Array<{ name: string; available: boolean }>>([])
async function fetchFeatures() {
  try {
    const f = await systemApi.getFeatures()
    features.value = Object.entries(f).map(([k, v]) => ({ name: k, available: !!v }))
  } catch { /* non-critical */ }
}

// ── Process Manager ──
const procs = ref<any[]>([])
const topProcs = ref<any[]>([])
const procSort = ref('cpu')
const procFilter = ref('')
const loadProcTree = ref(false)
const procTreeHtml = ref('')
const sysLoad = ref<any>({ load_avg: [] })

async function loadProcesses() {
  try { procs.value = (await systemApi.getProcesses(procSort.value, procFilter.value, 100)).processes || [] } catch {}
}

async function loadProcInfo() {
  try {
    const [tree, top, load] = await Promise.all([
      systemApi.getProcessTree(),
      systemApi.getTopProcesses(8),
      systemApi.getSystemLoad(),
    ])
    topProcs.value = top.top_cpu || []
    procTreeHtml.value = (top.top_cpu || []).map((p: any) =>
      `<span style="color:var(--red)">PID ${p.pid}</span> <span style="color:var(--accent)">${p.cpu.toFixed(1)}%</span> ${p.command}`
    ).join('<br>') + '<br><br>' + (tree.roots || []).map((r: any) =>
      `<span style="color:var(--green)">├ ${r.name}(${r.pid})</span>`
    ).join('<br>')
    sysLoad.value = load
  } catch {}
}

async function showProcDetail(pid: number) {
  try {
    const d = await systemApi.getProcessDetail(pid)
    procTreeHtml.value = `<pre style="font-size:12px; line-height:1.55">${JSON.stringify(d, null, 2)}</pre>`
    loadProcTree.value = true
  } catch { toast.error('获取进程详情失败') }
}

async function doKill(pid: number, sig: string) {
  try {
    const r = await systemApi.killProcess(pid, sig)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) loadProcesses()
  } catch { toast.error('操作失败') }
}

// Auto-refresh
const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(() => { loadProcesses(); loadProcInfo() }, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}

onMounted(() => { fetchFeatures(); loadProcesses(); loadProcInfo() })
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
