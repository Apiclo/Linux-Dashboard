<template>
  <div>
    <div class="page-title"><el-icon><Lightning /></el-icon>服务管理</div>

    <!-- 搜索与操作 -->
    <el-card shadow="never" class="mb-5">
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <el-input v-model="search" placeholder="搜索服务..." size="small" class="w-52" />
        <el-select v-model="filter" placeholder="状态" size="small" class="w-32" clearable>
          <el-option v-for="opt in filterOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-button size="small" plain @click="load"><el-icon><Refresh /></el-icon></el-button>
      </div>

      <el-divider content-position="left" class="!my-3">运行控制</el-divider>
      <div class="flex flex-wrap gap-3 mb-4">
        <el-button type="success" size="small" :disabled="!selected" @click="doAction('start')">
          <el-icon><VideoPlay /></el-icon>启动
        </el-button>
        <el-button type="danger" size="small" :disabled="!selected" @click="doAction('stop')">
          <el-icon><VideoPause /></el-icon>停止
        </el-button>
        <el-button type="warning" size="small" :disabled="!selected" @click="doAction('restart')">
          <el-icon><Refresh /></el-icon>重启
        </el-button>
      </div>

      <el-divider content-position="left" class="!my-3">开机控制</el-divider>
      <div class="flex flex-wrap gap-3 mb-4">
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
    <el-card shadow="never" class="mb-5" v-loading="loading">
      <el-table :data="filtered" stripe border size="small" max-height="500" highlight-current-row row-key="name" @row-click="onRowSelect">
        <el-table-column prop="name" label="服务" min-width="200">
          <template #default="{ row }"><span class="font-mono text-sm">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column prop="active" label="活跃" width="100">
          <template #default="{ row }"><el-tag :type="row.active?.startsWith('active') ? 'success' : row.active?.startsWith('failed') ? 'danger' : 'info'">{{ row.active }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="sub" label="子状态" width="100" />
        <el-table-column prop="description" label="描述" />
      </el-table>
    </el-card>

    <!-- 日志 -->
    <el-card shadow="never">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="flex items-center gap-2 font-semibold">
            <el-icon><Document /></el-icon>服务日志 {{ selected ? `(${selected})` : '' }}
          </span>
          <div class="flex items-center gap-2">
            <span class="text-xs" style="color: var(--text-2)">日志行数:</span>
            <el-select v-model="logLines" size="small" class="w-24" @change="selected && viewLogs()">
              <el-option :value="50" label="50 行" />
              <el-option :value="100" label="100 行" />
              <el-option :value="200" label="200 行" />
              <el-option :value="500" label="500 行" />
            </el-select>
            <el-button size="small" plain @click="viewLogs" :disabled="!selected"><el-icon><Refresh /></el-icon></el-button>
          </div>
        </div>
      </template>
      <div class="terminal">{{ logs || '选择服务后点击查看日志' }}</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, VideoPlay, VideoPause, CircleCheck, CircleClose, Document } from '@element-plus/icons-vue'
import { servicesApi } from '@/api/services'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import type { ServiceInfo } from '@/types/api'

const toast = useToast()
const { confirm: showConfirm } = useConfirm()
const loading = ref(false)
const services = ref<ServiceInfo[]>([])
const search = ref('')
const filter = ref('')
const selected = ref('')
const selectedRow = ref(null)
const logs = ref('')
const logLines = ref(150)

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

function onRowSelect(row: ServiceInfo) { selected.value = row.name }

async function load() {
  loading.value = true
  try { services.value = await servicesApi.getServices() } catch { toast.error('加载失败') }
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
  try { const r = await servicesApi.getLogs(selected.value, logLines.value); logs.value = r.logs || '无日志' } catch { logs.value = '获取失败' }
}

onMounted(load)
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
