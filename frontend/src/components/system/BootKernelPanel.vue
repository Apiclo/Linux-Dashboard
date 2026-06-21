<template>
  <div class="p-5">
    <div class="mb-3 text-sm" style="color: var(--text-2)">
      管理 GRUB 引导配置、内核启动参数、CPU 调节器和 I/O 调度器。修改后需重启生效。
    </div>

    <!-- ═══════════ 默认启动内核 ═══════════ -->
    <div class="p-3 mb-4 rounded-lg" style="background: var(--bg-0); border: 1px solid var(--border)">
      <div class="font-semibold text-sm mb-3">默认启动内核</div>
      <div v-if="grubCfg.entries.length" class="mb-3">
        <div class="text-xs mb-2" style="color: var(--text-2)">
          当前默认: <span class="font-mono" style="color: var(--accent)">{{ grubCfg.default || '(unset)' }}</span>
          <span class="ml-3" style="color: var(--text-2)">| 配置: {{ grubCfg.config_file }}</span>
          <span class="ml-1" style="color: var(--text-2)">| 检测: {{ grubCfg.grub_cfg_path }}</span>
        </div>
        <div class="flex gap-3 items-center flex-wrap">
          <el-select v-model="grubDefault" size="small" class="w-64" filterable>
            <el-option label="上次启动的内核 (saved)" value="saved" />
            <el-option-group label="已安装内核">
              <el-option v-for="e in grubCfg.entries" :key="e.index"
                :label="`[${e.index}] ${e.title}`" :value="String(e.index)" />
            </el-option-group>
          </el-select>
          <el-button size="small" type="primary" @click="doSetDefault" :loading="defaultSetting">
            <el-icon class="mr-1"><Check /></el-icon>设为默认
          </el-button>
        </div>
      </div>
      <div v-else class="text-sm" style="color: var(--text-2)">未检测到 GRUB 条目</div>
    </div>

    <!-- ═══════════ 内核引导参数 ═══════════ -->
    <div class="p-3 mb-4 rounded-lg" style="background: var(--bg-0); border: 1px solid var(--border)">
      <div class="font-semibold text-sm mb-3">内核引导参数</div>
      <div class="text-xs mb-2" style="color: var(--text-2)">
        当前: <code class="font-mono" style="color: var(--text-0)">{{ grubCfg.cmdline || '(空)' }}</code>
      </div>

      <!-- 预设 -->
      <div class="mb-3">
        <div class="text-xs mb-1" style="color: var(--text-2)">快速预设:</div>
        <div class="flex flex-wrap gap-2">
          <el-button v-for="(p, key) in cmdlinePresets" :key="key"
            size="small" plain @click="applyPreset(key)">
            {{ p.label }}
            <el-tooltip :content="`${p.desc}: ${p.params || '(清空所有参数)'}`" placement="top">
              <el-icon class="ml-1" style="font-size: 12px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </el-button>
        </div>
      </div>

      <!-- 自定义 -->
      <div class="flex gap-3 items-center">
        <el-input v-model="grubCmdline" placeholder="quiet splash intel_iommu=on ..." size="small" class="flex-1" @keyup.enter="doSetCmdline" />
        <el-button size="small" type="primary" @click="doSetCmdline" :loading="cmdlineSetting">应用</el-button>
      </div>
    </div>

    <!-- ═══════════ CPU 调节器 + I/O 调度器 ═══════════ -->
    <div class="grid grid-cols-12 gap-3 mb-4">
      <!-- CPU Governor -->
      <div class="col-span-12 md:col-span-6">
        <div class="p-3 rounded-lg" style="background: var(--bg-0); border: 1px solid var(--border)">
          <div class="font-semibold text-sm mb-3">CPU 频率调节器</div>
          <div class="text-xs mb-2" style="color: var(--text-2)">
            当前: <span class="font-mono" style="color: var(--accent)">{{ cpuGov.current || '未知' }}</span>
            <span v-if="cpuGov.driver" style="color: var(--text-2)"> (驱动: {{ cpuGov.driver }})</span>
          </div>
          <div class="flex gap-2 items-center flex-wrap">
            <el-button v-for="g in cpuGov.available" :key="g"
              size="small" :type="cpuGov.current === g ? 'primary' : 'default'"
              :plain="cpuGov.current !== g"
              @click="doSetGovernor(g)" :loading="governorSetting === g">
              {{ g }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- I/O Scheduler -->
      <div class="col-span-12 md:col-span-6">
        <div class="p-3 rounded-lg" style="background: var(--bg-0); border: 1px solid var(--border)">
          <div class="font-semibold text-sm mb-3">I/O 调度器</div>
          <div v-if="ioSched.devices.length" class="text-xs" style="max-height: 180px; overflow-y: auto">
            <div v-for="d in ioSched.devices" :key="d.name"
              class="flex items-center justify-between py-1 px-2 mb-1 rounded"
              style="background: var(--bg-2)">
              <span class="font-mono font-semibold">{{ d.name }}</span>
              <div class="flex gap-1 items-center">
                <span class="text-xs" style="color: var(--text-2)">{{ d.current }}</span>
                <el-select
                  :model-value="d.current"
                  @change="(v: string) => doSetScheduler(d.name, v)"
                  size="small"
                  class="w-28"
                >
                  <el-option v-for="s in d.available" :key="s" :label="s" :value="s" />
                </el-select>
              </div>
            </div>
          </div>
          <div v-else class="text-xs" style="color: var(--text-2)">无可用块设备</div>
        </div>
      </div>
    </div>

    <el-button size="small" plain @click="loadAll">刷新全部</el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Check, QuestionFilled } from '@element-plus/icons-vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

interface GrubEntry { index: number; title: string; file?: string }
interface GrubConfig { default: string; timeout: string; cmdline: string; entries: GrubEntry[]; config_file: string; grub_cfg_path: string; mkconfig_cmd: string }
interface CpuGov { available: string[]; current: string; driver: string }
interface IoDev { name: string; current: string; available: string[] }
interface CmdlinePreset { label: string; params: string; desc: string }

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

// GRUB
const grubCfg = ref<GrubConfig>({ default: '', timeout: '', cmdline: '', entries: [], config_file: '', grub_cfg_path: '', mkconfig_cmd: '' })
const grubDefault = ref('')
const grubCmdline = ref('')
const defaultSetting = ref(false)
const cmdlineSetting = ref(false)

// Presets
const cmdlinePresets = ref<Record<string, CmdlinePreset>>({})

// CPU
const cpuGov = ref<CpuGov>({ available: [], current: '', driver: '' })
const governorSetting = ref('')

// I/O
const ioSched = ref<{ devices: IoDev[] }>({ devices: [] })
const schedulerSetting = ref('')

async function loadAll() {
  await Promise.all([loadGrub(), loadPresets(), loadCpu(), loadIo()])
}

async function loadGrub() {
  try { grubCfg.value = await systemApi.getGrubConfig(); grubDefault.value = grubCfg.value.default; grubCmdline.value = grubCfg.value.cmdline } catch {}
}

async function loadPresets() {
  try { cmdlinePresets.value = (await systemApi.getCmdlinePresets()).presets || {} } catch {}
}

async function loadCpu() {
  try { cpuGov.value = await systemApi.getCpuGovernor() } catch {}
}

async function loadIo() {
  try { ioSched.value = await systemApi.getIoScheduler() } catch {}
}

async function doSetDefault() {
  if (!(await showConfirm('设置默认内核', `确定修改默认启动内核为: ${grubDefault.value}？`))) return
  defaultSetting.value = true
  try {
    const r = await systemApi.setGrubDefault(grubDefault.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadGrub()
  } finally { defaultSetting.value = false }
}

function applyPreset(key: string) {
  const p = cmdlinePresets.value[key]
  if (p) grubCmdline.value = p.params
}

async function doSetCmdline() {
  if (!(await showConfirm('设置引导参数', `确定修改内核引导参数？\n\n${grubCmdline.value || '(清空所有参数)'}`))) return
  cmdlineSetting.value = true
  try {
    const r = await systemApi.setGrubCmdline(grubCmdline.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadGrub()
  } finally { cmdlineSetting.value = false }
}

async function doSetGovernor(g: string) {
  governorSetting.value = g
  try {
    const r = await systemApi.setCpuGovernor(g)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadCpu()
  } finally { governorSetting.value = '' }
}

async function doSetScheduler(dev: string, sched: string) {
  schedulerSetting.value = dev
  try {
    const r = await systemApi.setIoScheduler(dev, sched)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadIo()
  } finally { schedulerSetting.value = '' }
}

defineExpose({ loadAll })
onMounted(loadAll)
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
