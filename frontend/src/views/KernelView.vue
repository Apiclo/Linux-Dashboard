<template>
  <div>
    <div class="page-title">
      <el-icon><Cpu /></el-icon>内核调优
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新 (30s)" />
    </div>

    <FeatureStatus :features="features" />

    <!-- Sysctl -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Setting /></el-icon>内核参数 (Sysctl)</span>
          <el-button size="small" plain @click="loadSysctl">刷新</el-button>
        </div>
      </template>
      <el-input v-model="sysctlQueryRaw" placeholder="搜索参数..." class="w-full mb-4" size="small" />
      <el-table :data="paginatedSysctlRows" size="small" stripe border height="350px" @sort-change="onSysctlSort">
        <el-table-column prop="key" label="参数" min-width="300" sortable="custom">
          <template #default="scope"><span class="mono text-sm">{{ scope.row.key }}</span></template>
        </el-table-column>
        <el-table-column prop="value" label="值" min-width="200" sortable="custom">
          <template #default="scope"><span class="mono text-sm">{{ scope.row.value }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="scope"><el-button size="small" plain @click="openEdit(scope.row.key, scope.row.value)">修改</el-button></template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="sysctlTotal > sysctlPageSize"
        class="mt-4"
        layout="prev, pager, next, sizes"
        :page-sizes="[20, 50, 100, 200]"
        :page-size="sysctlPageSize"
        :total="sysctlTotal"
        :current-page="sysctlPage"
        size="small"
        @size-change="onSysctlSizeChange"
        @current-change="onSysctlPageChange"
      />
    </el-card>

    <!-- Kernel Modules -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Box /></el-icon>内核模块</span>
      </template>
      <KernelModulesPanel />
    </el-card>

    <!-- Boot & Kernel -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Cpu /></el-icon>引导 & 内核调优</span>
      </template>
      <BootKernelPanel />
    </el-card>

    <!-- System Optimization -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Lightning /></el-icon>系统优化方案</span>
      </template>
      <SystemOptimizationPanel />
    </el-card>

    <!-- Sysctl Edit Dialog -->
    <el-dialog v-model="editModal" title="修改 Sysctl 参数" width="420px">
      <div class="mb-3"><strong>参数:</strong> <span class="mono">{{ editKey }}</span></div>
      <div class="mb-4"><strong>当前值:</strong> {{ editCurrent }}</div>
      <el-input v-model="editValue" placeholder="新值" class="w-full" @keyup.enter="saveEdit" />
      <template #footer>
        <el-button plain @click="editModal = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useDebounce } from '@/composables/useDebounce'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import KernelModulesPanel from '@/components/system/KernelModulesPanel.vue'
import BootKernelPanel from '@/components/system/BootKernelPanel.vue'
import SystemOptimizationPanel from '@/components/system/SystemOptimizationPanel.vue'
import { Setting, Box, Cpu, Lightning } from '@element-plus/icons-vue'

const toast = useToast()

// Features
const features = ref<Array<{ name: string; available: boolean }>>([])
async function fetchFeatures() {
  try {
    const f = await systemApi.getFeatures()
    features.value = Object.entries(f).map(([k, v]) => ({ name: k, available: !!v }))
  } catch { /* non-critical */ }
}

// ── Sysctl ──
const sysctl = ref<Record<string, string>>({})
const sysctlQueryRaw = ref('')
const sysctlQuery = useDebounce(sysctlQueryRaw, 300)
const sysctlPage = ref(1)
const sysctlPageSize = ref(50)
const sysctlSortKey = ref('')
const sysctlSortOrder = ref<'ascending' | 'descending' | null>(null)

const sysctlRows = computed(() => {
  const q = sysctlQuery.value.toLowerCase()
  const entries = Object.entries(sysctl.value)
    .filter(([k]) => !q || k.toLowerCase().includes(q))
    .map(([key, value]) => ({ key, value }))
  if (sysctlSortKey.value && sysctlSortOrder.value) {
    entries.sort((a, b) => {
      const va = a[sysctlSortKey.value as keyof typeof a]
      const vb = b[sysctlSortKey.value as keyof typeof a]
      if (va < vb) return sysctlSortOrder.value === 'ascending' ? -1 : 1
      if (va > vb) return sysctlSortOrder.value === 'ascending' ? 1 : -1
      return 0
    })
  }
  return entries.slice(0, 300)
})

const sysctlTotal = computed(() => sysctlRows.value.length)

const paginatedSysctlRows = computed(() => {
  const start = (sysctlPage.value - 1) * sysctlPageSize.value
  return sysctlRows.value.slice(start, start + sysctlPageSize.value)
})

function onSysctlSort({ prop, order }: { prop: string; order: string }) {
  sysctlSortKey.value = prop
  sysctlSortOrder.value = order as 'ascending' | 'descending' | null
  sysctlPage.value = 1
}

function onSysctlSizeChange(s: number) { sysctlPageSize.value = s; sysctlPage.value = 1 }
function onSysctlPageChange(p: number) { sysctlPage.value = p }

async function loadSysctl() {
  try { sysctl.value = await systemApi.getSysctl() } catch { toast.error('加载 Sysctl 参数失败') }
}

// Edit dialog
const editModal = ref(false)
const editKey = ref('')
const editCurrent = ref('')
const editValue = ref('')

function openEdit(k: string, v: string) {
  editKey.value = k; editCurrent.value = v; editValue.value = v; editModal.value = true
}

async function saveEdit() {
  const r = await systemApi.setSysctl(editKey.value, editValue.value)
  toast.show(r.success ? '已设置' : '失败', r.success ? 'success' : 'error')
  editModal.value = false
  if (r.success) sysctl.value = await systemApi.getSysctl()
}

// Auto-refresh
const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(loadSysctl, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}

onMounted(() => { fetchFeatures(); loadSysctl() })
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>

<style scoped>
.mono { font-family: 'JetBrains Mono', monospace; }
</style>
