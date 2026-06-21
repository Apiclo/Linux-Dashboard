<template>
  <div>
    <div class="page-title"><el-icon><EditPen /></el-icon>配置编辑</div>

    <FeatureStatus :features="features" />

    <!-- 预设选择 -->
    <div class="flex gap-3 mb-5 items-center">
      <el-select v-model="preset" placeholder="选择预设" size="small" class="w-48" clearable @change="loadConfig" :loading="presetsLoading">
        <el-option v-for="opt in presetOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-input v-model="customPath" placeholder="或输入自定义路径" class="flex-1" size="small" @keyup.enter="loadConfig" />
      <el-button size="small" @click="loadConfig"><el-icon><FolderOpened /></el-icon>加载</el-button>
    </div>

    <!-- 快速参数 -->
    <el-card v-if="preset && presets[preset]?.keys?.length" shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Setting /></el-icon>快速参数</span>
      </template>
      <el-form label-width="140px">
        <el-form-item v-for="k in presets[preset].keys" :key="k.key" :label="k.key">
          <template #label>
            <span class="font-mono text-sm" style="color: var(--accent)">{{ k.key }}</span>
          </template>
          <!-- bool → Switch -->
          <div v-if="k.type === 'bool'" class="flex items-center gap-3 w-full">
            <span class="text-xs" style="color: var(--text-1); min-width: 60px">{{ k.desc }}</span>
            <el-switch
              v-model="values[k.key]"
              :active-value="k.true_val || 'yes'"
              :inactive-value="k.false_val || 'no'"
              size="small"
              inline-prompt
              :active-text="k.true_val || 'yes'"
              :inactive-text="k.false_val || 'no'"
              @change="queueToggle(k.key)"
            />
          </div>
          <!-- number → InputNumber-style -->
          <div v-else-if="k.type === 'number'" class="flex items-center gap-3 w-full">
            <span class="text-xs" style="color: var(--text-1); min-width: 60px">{{ k.desc }}</span>
            <el-input v-model="values[k.key]" size="small" style="width: 160px" @keyup.enter="setParam(k.key)" />
            <el-button size="small" plain @click="setParam(k.key)">设置</el-button>
          </div>
          <!-- text / default -->
          <div v-else class="flex items-center gap-3 w-full">
            <span class="flex-1 text-xs" style="color: var(--text-1)">{{ k.desc }}</span>
            <el-input v-model="values[k.key]" size="small" style="width: 240px; max-width: 320px" @keyup.enter="setParam(k.key)" />
            <el-button size="small" plain @click="setParam(k.key)">设置</el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 文件编辑器 -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Document /></el-icon>文件编辑器</span>
          <span class="font-mono text-sm" style="color: var(--text-2)">{{ filePath || '-' }}</span>
        </div>
      </template>
      <el-input v-model="content" type="textarea" :rows="20" class="w-full mb-3 mono mono-textarea" />
      <div class="flex gap-4 items-center">
        <el-button size="small" plain @click="loadConfig"><el-icon><Refresh /></el-icon>刷新</el-button>
        <el-button size="small" @click="saveConfig" :disabled="!filePath"><el-icon><Check /></el-icon>保存</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { systemApi } from '@/api/system'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { FolderOpened, Setting, Document, Refresh, Check } from '@element-plus/icons-vue'
import { configApi } from '@/api/config'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import type { ConfigPreset } from '@/types/api'

const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['sudo','pam'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }
const { confirm: showConfirm } = useConfirm()
const presets = ref<Record<string, ConfigPreset>>({})
const preset = ref('')
const customPath = ref('')
const filePath = ref('')
const content = ref('')
const values = ref<Record<string, string>>({})
const configLoading = ref(false)
const presetsLoading = ref(true)

// ── Toggle debounce: batch boolean toggle changes ──
const toggleQueue = ref<Record<string, string>>({})
let toggleTimer: ReturnType<typeof setTimeout> | null = null

function queueToggle(key: string) {
  if (configLoading.value) return
  toggleQueue.value[key] = values.value[key] || ''
  if (toggleTimer) clearTimeout(toggleTimer)
  toggleTimer = setTimeout(() => flushToggles(), 500)
}

async function flushToggles() {
  const entries = Object.entries(toggleQueue.value)
  toggleQueue.value = {}
  if (!entries.length) return
  let successCount = 0
  let failCount = 0
  for (const [key, val] of entries) {
    try {
      const r = await configApi.setParam(filePath.value, key, val)
      if (r.success) { successCount++; content.value = r.content }
      else failCount++
    } catch { failCount++ }
  }
  if (successCount > 0 && failCount === 0) {
    toast.show(`已应用 ${successCount} 项设置`, 'success')
  } else if (successCount > 0) {
    toast.show(`${successCount}/${entries.length} 项成功`, 'warn')
  } else {
    toast.error('设置失败')
  }
}

const presetOptions = computed(() => Object.keys(presets.value).map(k => ({ label: k, value: k })))

async function loadPresets() {
  presetsLoading.value = true
  try { presets.value = await configApi.getPresets() } catch {} finally {
    presetsLoading.value = false
  }
}

async function loadConfig() {
  let path = customPath.value || (preset.value && presets.value[preset.value]?.path) || ''
  if (!path) return
  filePath.value = path
  configLoading.value = true
  try {
    const r = await configApi.read(path, preset.value)
    content.value = r.success ? r.content : `# 无法读取: ${path}`
    values.value = r.parsed || {}
  } catch { toast.error('加载失败') } finally {
    configLoading.value = false
  }
}

async function setParam(key: string) {
  if (configLoading.value) return
  const val = (values.value[key] || '').trim()
  if (!val) return toast.warning('请输入值')
  try {
    const r = await configApi.setParam(filePath.value, key, val)
    toast.show(r.success ? `已设置 ${key}` : '失败', r.success ? 'success' : 'error')
    if (r.success) content.value = r.content
  } catch { toast.error('失败') }
}

async function saveConfig() {
  if (!filePath.value) return
  if (!(await showConfirm('保存', `确定保存 ${filePath.value}？`))) return
  try {
    const r = await configApi.save(filePath.value, content.value)
    toast.show(r.success ? '已保存' : '失败', r.success ? 'success' : 'error')
  } catch { toast.error('失败') }
}

onMounted(() => { loadPresets(); fetchFeatures() })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
