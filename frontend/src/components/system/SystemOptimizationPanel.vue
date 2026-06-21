<template>
  <div class="p-5">
    <div class="mb-3 text-sm" style="color: var(--text-2)">
      选择优化方案，勾选要应用的项（默认全选），然后点击应用。
    </div>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane v-for="(info, key) in profiles" :key="key" :label="info.label" :name="key">
        <template #label>
          <span class="flex items-center gap-2">
            <el-icon><component :is="key === 'server' ? Monitor : Cpu" /></el-icon>
            {{ info.label }}
          </span>
        </template>
      </el-tab-pane>
      <el-tab-pane name="custom">
        <template #label>
          <span class="flex items-center gap-2"><el-icon><Setting /></el-icon>自定义</span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- ═══════════ 场景模式 ═══════════ -->
    <template v-if="activeTab !== 'custom'">
      <div v-if="loading" class="text-center py-6" style="color: var(--text-2)">
        <el-icon class="is-loading" :size="20"><Loading /></el-icon> 正在分析...
      </div>

      <div v-else-if="preview">
        <div class="text-sm mb-3" style="color: var(--text-1)">{{ profiles[activeTab]?.desc }}</div>

        <!-- sysctl 变更 — 带逐项勾选 -->
        <div v-if="preview.sysctl_changes?.length" class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="font-semibold text-sm">内核参数</span>
            <el-checkbox v-model="allSysctlChecked" :indeterminate="sysctlPartial" @change="toggleAllSysctl">
              全选 ({{ checkedSysctlCount }}/{{ preview.sysctl_changes.length }})
            </el-checkbox>
          </div>
          <el-table :data="preview.sysctl_changes" size="small" stripe border max-height="300" @selection-change="onSysctlSelect">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="key" label="参数" min-width="240">
              <template #default="{ row }"><span class="font-mono text-sm">{{ row.key }}</span></template>
            </el-table-column>
            <el-table-column label="当前 → 推荐" min-width="260">
              <template #default="{ row }">
                <span class="font-mono text-xs" :style="{ color: row.will_change ? 'var(--yellow)' : 'var(--text-2)' }">{{ row.current || '-' }}</span>
                <el-icon v-if="row.will_change" style="margin: 0 4px; font-size:12px; color: var(--text-2)"><ArrowRight /></el-icon>
                <span v-if="row.will_change" class="font-mono text-xs" style="color: var(--green)">{{ row.recommended }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.will_change ? 'warning' : 'info'" size="small">{{ row.will_change ? '将变更' : '已匹配' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 服务变更 — 带逐项勾选 -->
        <div v-if="preview.svc_changes?.length" class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="font-semibold text-sm">服务</span>
            <el-checkbox v-model="allSvcsChecked" :indeterminate="svcsPartial" @change="toggleAllSvcs">
              全选 ({{ checkedSvcsCount }}/{{ preview.svc_changes.length }})
            </el-checkbox>
          </div>
          <el-table :data="preview.svc_changes" size="small" stripe border max-height="250" @selection-change="onSvcsSelect">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="name" label="服务名" min-width="160">
              <template #default="{ row }"><span class="font-mono text-sm">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column label="已启用" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'warning' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="运行中" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.active ? 'warning' : 'info'" size="small">{{ row.active ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.will_disable ? 'danger' : 'info'" size="small">{{ row.will_disable ? '将禁用' : '无操作' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="flex items-center gap-4 p-3 rounded-lg mb-4" style="background: var(--bg-0)">
          <span class="text-sm">
            已选 <strong>{{ checkedSysctlCount + checkedSvcsCount }}</strong> 项
            （共 {{ sysctlChangeCount + svcChangeCount }} 项变更可应用）
          </span>
        </div>

        <el-button type="primary" @click="applyProfile" :loading="applying"
          :disabled="checkedSysctlCount + checkedSvcsCount === 0">
          <el-icon class="mr-1"><Check /></el-icon>应用已选项
        </el-button>
      </div>
    </template>

    <!-- ═══════════ 自定义模式 ═══════════ -->
    <template v-else>
      <div class="font-semibold text-sm mb-3 mt-2">内核参数</div>
      <div v-if="customLoading" class="text-center py-4" style="color: var(--text-2)">
        <el-icon class="is-loading" :size="16"><Loading /></el-icon> 加载中...
      </div>
      <div v-else>
        <div v-for="p in customParams" :key="p.key" class="mb-3 p-3 rounded-lg" style="background: var(--bg-0)">
          <div class="flex items-center justify-between mb-2">
            <span class="font-mono text-sm font-semibold">{{ p.key }}</span>
            <el-tag size="small" type="info">推荐: {{ p.recommended }}</el-tag>
          </div>
          <div class="mb-2" style="color: var(--text-2); font-size: 13px">{{ p.desc }}</div>
          <div class="flex items-center gap-3">
            <span style="color: var(--text-2); font-size: 13px">当前值: <span class="font-mono font-semibold">{{ p.current }}</span></span>
            <div class="flex-1">
              <el-slider v-if="p.type === 'range'" v-model="customValues[p.key]" :min="p.min || 0" :max="p.max || 100" :marks="{ [p.recommended]: '推荐' }" size="small" />
              <el-select v-else-if="p.type === 'select'" v-model="customValues[p.key]" size="small" style="width: 200px">
                <el-option v-for="opt in p.options" :key="opt" :label="opt" :value="opt" />
              </el-select>
              <el-input v-else v-model="customValues[p.key]" size="small" style="width: 200px" :placeholder="'推荐: ' + p.recommended" />
            </div>
          </div>
        </div>
        <el-button size="small" type="primary" @click="applyCustomSysctl" :loading="customApplying">应用内核参数</el-button>
      </div>

      <el-divider />
      <div class="font-semibold text-sm mb-3">服务优化</div>
      <div v-if="customSvcs.length">
        <el-table :data="customSvcs" size="small" stripe border class="mb-3"
          @selection-change="onCustomSvcsSelect">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="name" label="服务名" width="180">
            <template #default="{ row }"><span class="font-mono">{{ row.name }}</span></template>
          </el-table-column>
          <el-table-column prop="desc" label="描述" min-width="200" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.active ? 'success' : 'info'" size="small">{{ row.active ? '运行中' : '未运行' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-button size="small" type="warning" @click="applyCustomSvcs" :loading="customApplying" :disabled="!customCheckedSvcs.length">
          <el-icon class="mr-1"><Lightning /></el-icon>禁用已选服务 ({{ customCheckedSvcs.length }})
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Loading, Check, Monitor, Cpu, Setting, Lightning, ArrowRight } from '@element-plus/icons-vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

interface ProfileInfo { label: string; desc: string }
interface SysctlChange { key: string; current: string; recommended: string; will_change: boolean }
interface SvcChange { name: string; enabled: boolean; active: boolean; will_disable: boolean }
interface PreviewData { success: boolean; profile: string; label: string; desc: string; sysctl_changes: SysctlChange[]; svc_changes: SvcChange[] }
interface CustomParam { key: string; current: string; desc: string; recommended: string; type: string; min?: number; max?: number; options?: string[] }
interface CustomSvc { name: string; desc: string; safe: boolean; enabled: boolean; active: boolean }

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

const profiles = ref<Record<string, ProfileInfo>>({})
const activeTab = ref('server')
const preview = ref<PreviewData | null>(null)
const loading = ref(false)
const applying = ref(false)

// Per-item selection state
const checkedSysctlKeys = ref<Set<string>>(new Set())
const checkedSvcNames = ref<Set<string>>(new Set())

const sysctlChangeCount = computed(() => preview.value?.sysctl_changes?.filter(c => c.will_change).length ?? 0)
const svcChangeCount = computed(() => preview.value?.svc_changes?.filter(c => c.will_disable).length ?? 0)
const checkedSysctlCount = computed(() => checkedSysctlKeys.value.size)
const checkedSvcsCount = computed(() => checkedSvcNames.value.size)

const allSysctlChecked = computed(() =>
  preview.value ? checkedSysctlKeys.value.size === preview.value.sysctl_changes.length && preview.value.sysctl_changes.length > 0 : false)
const sysctlPartial = computed(() =>
  checkedSysctlKeys.value.size > 0 && checkedSysctlKeys.value.size < (preview.value?.sysctl_changes?.length ?? 0))
const allSvcsChecked = computed(() =>
  preview.value ? checkedSvcNames.value.size === preview.value.svc_changes.length && preview.value.svc_changes.length > 0 : false)
const svcsPartial = computed(() =>
  checkedSvcNames.value.size > 0 && checkedSvcNames.value.size < (preview.value?.svc_changes?.length ?? 0))

function onSysctlSelect(rows: SysctlChange[]) { checkedSysctlKeys.value = new Set(rows.map(r => r.key)) }
function onSvcsSelect(rows: SvcChange[]) { checkedSvcNames.value = new Set(rows.map(r => r.name)) }

function toggleAllSysctl(v: boolean) {
  if (v && preview.value) checkedSysctlKeys.value = new Set(preview.value.sysctl_changes.map(r => r.key))
  else checkedSysctlKeys.value = new Set()
}
function toggleAllSvcs(v: boolean) {
  if (v && preview.value) checkedSvcNames.value = new Set(preview.value.svc_changes.map(r => r.name))
  else checkedSvcNames.value = new Set()
}

async function loadProfiles() {
  try {
    const r = await systemApi.getOptimizationProfiles()
    profiles.value = r.profiles || {}
    const keys = Object.keys(profiles.value)
    if (keys.length && !profiles.value[activeTab.value]) activeTab.value = keys[0]
    if (activeTab.value !== 'custom') await loadPreview()
  } catch { /* ignore */ }
}

async function loadPreview() {
  loading.value = true
  try {
    preview.value = await systemApi.getOptimizationPreview(activeTab.value)
    // 默认全选
    if (preview.value) {
      checkedSysctlKeys.value = new Set(preview.value.sysctl_changes.map(r => r.key))
      checkedSvcNames.value = new Set(preview.value.svc_changes.map(r => r.name))
    }
  } catch { loading.value = false }
  loading.value = false
}

async function applyProfile() {
  const sysctlKeys = [...checkedSysctlKeys.value]
  const svcNames = [...checkedSvcNames.value]
  if (!sysctlKeys.length && !svcNames.length) return

  if (!(await showConfirm('应用优化',
    `确定应用「${profiles.value[activeTab.value]?.label}」方案的 ${sysctlKeys.length + svcNames.length} 个已选项吗？`))) return

  applying.value = true
  try {
    const r = await systemApi.applyOptimizationProfile(activeTab.value, sysctlKeys, svcNames)
    const sysctlOk = r.sysctl_results?.filter(x => x.success).length ?? 0
    const svcOk = r.svc_results?.filter(x => x.success).length ?? 0
    toast.show(`已应用: ${sysctlOk}/${sysctlKeys.length} 参数 + ${svcOk}/${svcNames.length} 服务`,
      sysctlOk + svcOk > 0 ? 'success' : 'error')
    await loadPreview()
  } finally { applying.value = false }
}

function onTabChange(name: string) {
  if (name !== 'custom') loadPreview()
  else if (!customParams.value.length) loadCustomData()
}

// Custom tab
const customParams = ref<CustomParam[]>([])
const customValues = ref<Record<string, any>>({})
const customSvcs = ref<CustomSvc[]>([])
const customCheckedSvcs = ref<string[]>([])
const customLoading = ref(false)
const customApplying = ref(false)

function onCustomSvcsSelect(rows: CustomSvc[]) { customCheckedSvcs.value = rows.map(r => r.name) }

async function loadCustomData() {
  customLoading.value = true
  try {
    const [qp, svc] = await Promise.all([systemApi.getQuickParams(), systemApi.getServiceOptimize()])
    customParams.value = qp.params || []
    customSvcs.value = svc.services || []
    customCheckedSvcs.value = svc.services?.filter(s => s.active).map(s => s.name) || []
    const vals: Record<string, any> = {}
    for (const p of customParams.value) vals[p.key] = p.type === 'range' ? parseInt(p.current) || 0 : p.current
    customValues.value = vals
  } catch { /* ignore */ }
  customLoading.value = false
}

async function applyCustomSysctl() {
  if (!(await showConfirm('应用参数', '确定应用自定义内核参数？'))) return
  customApplying.value = true
  try {
    const p: Record<string, string> = {}
    for (const [k, v] of Object.entries(customValues.value)) p[k] = String(v)
    const r = await systemApi.applyQuickParams(p)
    const ok = r.results.filter(x => x.success).length
    toast.show(`已设置 ${ok}/${r.results.length} 个参数`, ok > 0 ? 'success' : 'error')
    await loadCustomData()
  } finally { customApplying.value = false }
}

async function applyCustomSvcs() {
  if (!customCheckedSvcs.value.length) return
  if (!(await showConfirm('服务优化', `确定禁用 ${customCheckedSvcs.value.length} 个已选服务吗？`))) return
  customApplying.value = true
  try {
    const r = await systemApi.runServiceOptimize()
    const ok = r.results.filter(x => x.success).length
    toast.show(`已禁用 ${ok}/${r.results.length} 个服务`, ok > 0 ? 'success' : 'error')
    await loadCustomData()
  } finally { customApplying.value = false }
}

defineExpose({ loadProfiles })
onMounted(loadProfiles)
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
