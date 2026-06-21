<template>
  <div class="p-5">
    <div class="mb-3 text-sm" style="color: var(--text-2)">
      常用服务器优化参数，修改后立即生效。推荐值适用于大多数服务器场景。
    </div>
    <div v-for="param in params" :key="param.key" class="mb-3 p-3 rounded-lg" style="background: var(--bg-1)">
      <div class="flex items-center justify-between mb-2">
        <span class="font-mono text-sm font-semibold">{{ param.key }}</span>
        <el-tag size="small" type="info">推荐: {{ param.recommended }}</el-tag>
      </div>
      <div class="mb-3" style="color: var(--text-2); font-size: 13px">{{ param.desc }}</div>
      <div class="flex items-center gap-3">
        <span style="color: var(--text-2); font-size: 13px">当前值: <span class="font-mono font-semibold">{{ param.current }}</span></span>
        <div class="flex-1">
          <el-slider
            v-if="param.type === 'range'"
            v-model="values[param.key]"
            :min="param.min || 0"
            :max="param.max || 100"
            :marks="{ [param.recommended]: '推荐' }"
            size="small"
          />
          <el-select
            v-else-if="param.type === 'select'"
            v-model="values[param.key]"
            size="small"
            style="width: 200px"
          >
            <el-option v-for="opt in param.options" :key="opt" :label="opt" :value="opt" />
          </el-select>
          <el-input
            v-else
            v-model="values[param.key]"
            size="small"
            style="width: 200px"
            :placeholder="'推荐: ' + param.recommended"
          />
        </div>
      </div>
    </div>
    <el-empty v-if="!params.length" description="暂无参数" :image-size="60" />
    <div class="flex gap-3 mt-3 items-center">
      <el-button size="small" type="primary" @click="applyRecommended" :loading="loading">应用推荐值</el-button>
      <el-button size="small" type="success" @click="applyCustom" :loading="loading">应用自定义值</el-button>
      <el-button size="small" plain @click="load">刷新</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

interface QuickParam {
  key: string
  current: string
  desc: string
  recommended: string
  type: string
  min?: number
  max?: number
  options?: string[]
}

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

const params = ref<QuickParam[]>([])
const values = ref<Record<string, any>>({})
const loading = ref(false)

async function load() {
  try {
    const r = await systemApi.getQuickParams()
    params.value = r.params || []
    const vals: Record<string, any> = {}
    for (const p of params.value) {
      vals[p.key] = p.type === 'range' ? parseInt(p.current) || 0 : p.current
    }
    values.value = vals
  } catch { /* ignore */ }
}

async function applyRecommended() {
  if (!(await showConfirm('应用推荐值', '确定要将所有参数设置为推荐值吗？'))) return
  loading.value = true
  try {
    const p: Record<string, string> = {}
    for (const param of params.value) p[param.key] = param.recommended
    const r = await systemApi.applyQuickParams(p)
    const ok = r.results.filter((x: unknown) => (x as Record<string, unknown>).success).length
    toast.show(`已设置 ${ok}/${r.results.length} 个参数`, ok > 0 ? 'success' : 'error')
    await load()
  } finally { loading.value = false }
}

async function applyCustom() {
  loading.value = true
  try {
    const p: Record<string, string> = {}
    for (const [key, val] of Object.entries(values.value)) p[key] = String(val)
    const r = await systemApi.applyQuickParams(p)
    const ok = r.results.filter((x: unknown) => (x as Record<string, unknown>).success).length
    toast.show(`已设置 ${ok}/${r.results.length} 个参数`, ok > 0 ? 'success' : 'error')
    await load()
  } finally { loading.value = false }
}

defineExpose({ load })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
