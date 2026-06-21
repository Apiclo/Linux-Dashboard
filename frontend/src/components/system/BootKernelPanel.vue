<template>
  <div class="boot-panel">
    <div class="panel-description">
      管理 GRUB 引导配置、内核启动参数、CPU 调节器和 I/O 调度器。修改后需重启生效。
    </div>

    <!-- ═══════════ 引导加载器选择 ═══════════ -->
    <div v-if="grubCfg.available?.length > 1" class="bootloader-bar">
      <span class="bootloader-label">引导加载器</span>
      <el-radio-group v-model="activeBootloader" size="small" @change="switchBootloader">
        <el-radio-button v-for="bl in grubCfg.available" :key="bl" :value="bl">
          {{ bl === 'systemd-boot' ? 'systemd-boot' : bl === 'grub' ? 'GRUB' : bl === 'refind' ? 'rEFInd' : bl }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- ═══════════ 默认启动项 ═══════════ -->
    <div class="section-box">
      <div class="section-header">
        <span class="section-title">默认启动项</span>
        <el-tag size="small" type="info">
          {{ grubCfg.bootloader === 'systemd-boot' ? 'systemd-boot' : grubCfg.bootloader === 'grub' ? 'GRUB' : grubCfg.bootloader === 'refind' ? 'rEFInd' : grubCfg.bootloader || '未知' }}
        </el-tag>
      </div>

      <div v-if="loadError" class="panel-error">{{ loadError }}</div>

      <!-- Current default info -->
      <div class="current-default-row">
        <span class="info-label-sm">当前默认</span>
        <el-tooltip v-if="grubCfg.default && grubCfg.default.length > 60" :content="grubCfg.default" placement="top">
          <el-tag type="success" size="small" effect="dark" class="font-mono clickable">{{ grubCfg.default.slice(0, 60) }}...</el-tag>
        </el-tooltip>
        <el-tag v-else-if="grubCfg.default" type="success" size="small" effect="dark" class="font-mono">{{ grubCfg.default }}</el-tag>
        <span v-else class="font-mono text-muted">(未设置)</span>

        <span class="meta-divider">·</span>
        <span class="text-muted text-sm">配置: {{ grubCfg.config_file || '—' }}</span>
      </div>

      <!-- Entry table -->
      <div v-if="grubCfg.entries.length" class="entry-section">
        <el-table
          :data="grubCfg.entries"
          size="small"
          stripe
          border
          max-height="280"
          highlight-current-row
          @row-click="onEntryClick"
          class="entry-table"
        >
          <el-table-column label="#" width="50" align="center">
            <template #default="{ row }">
              <span class="font-mono text-muted text-sm">{{ row.index }}</span>
            </template>
          </el-table-column>
          <el-table-column label="启动项" min-width="280">
            <template #default="{ row }">
              <el-tooltip v-if="row.title.length > 80" :content="row.title" placement="top">
                <span class="font-mono text-sm">{{ row.title.slice(0, 80) }}...</span>
              </el-tooltip>
              <span v-else class="font-mono text-sm">{{ row.title }}</span>
              <el-tag v-if="String(row.index) === grubDefault || row.title === grubCfg.default" type="success" size="small" effect="dark" class="ml-2">
                当前默认
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="grubCfg.bootloader === 'systemd-boot'" label="内核" width="180">
            <template #default="{ row }">
              <span v-if="row.linux" class="font-mono text-xs text-muted">{{ row.linux.split('/').pop() }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" text @click.stop="selectAndSet(row)">
                {{ (String(row.index) === grubDefault || row.title === grubCfg.default) ? '当前默认' : '选择此项' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- Set default controls -->
        <div class="set-default-row">
          <el-select v-model="grubDefault" size="small" class="entry-select" filterable placeholder="选择默认启动项">
            <el-option v-if="grubCfg.bootloader === 'grub'" label="上次启动的内核 (saved)" value="saved" />
            <el-option-group label="已安装系统">
              <el-option v-for="e in grubCfg.entries" :key="e.index"
                :label="`[${e.index}] ${e.title.length > 60 ? e.title.slice(0, 60) + '...' : e.title}`" :value="String(e.index)">
                <template #default>
                  <el-tooltip v-if="e.title.length > 60" :content="e.title" placement="top">
                    <span>[{{ e.index }}] {{ e.title.slice(0, 60) }}...</span>
                  </el-tooltip>
                  <span v-else>[{{ e.index }}] {{ e.title }}</span>
                </template>
              </el-option>
            </el-option-group>
          </el-select>
          <el-button size="small" type="primary" @click="doSetDefault" :loading="defaultSetting">
            <el-icon class="mr-1"><Check /></el-icon>设为默认
          </el-button>
        </div>
      </div>

      <el-empty v-else :description="grubCfg.bootloader === 'unknown' ? '未检测到引导加载器' : '未检测到 ' + (grubCfg.bootloader || 'GRUB') + ' 启动条目'" :image-size="60" />
    </div>

    <!-- ═══════════ 内核引导参数 ═══════════ -->
    <div class="section-box">
      <div class="section-header">
        <span class="section-title">内核引导参数</span>
      </div>

      <div class="current-cmdline">
        <span class="info-label-sm">当前参数</span>
        <code class="cmdline-value">{{ grubCfg.cmdline || '(空)' }}</code>
      </div>

      <!-- Presets -->
      <div class="presets-section">
        <span class="info-label-sm">快速预设</span>
        <div class="preset-buttons">
          <el-button v-for="(p, key) in cmdlinePresets" :key="key"
            size="small" plain @click="applyPreset(key)">
            {{ p.label }}
            <el-tooltip :content="`${p.desc}: ${p.params || '(清空所有参数)'}`" placement="top">
              <el-icon class="ml-1" style="font-size: 12px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </el-button>
        </div>
      </div>

      <!-- Custom input -->
      <div class="custom-cmdline">
        <el-input v-model="grubCmdline" placeholder="quiet splash intel_iommu=on ..." size="small" class="cmdline-input" @keyup.enter="doSetCmdline" />
        <el-button size="small" type="primary" @click="doSetCmdline" :loading="cmdlineSetting">应用</el-button>
      </div>
    </div>

    <!-- ═══════════ CPU 调节器 + I/O 调度器 ═══════════ -->
    <div class="two-col-grid">
      <!-- CPU Governor -->
      <div class="section-box">
        <div class="section-header">
          <span class="section-title">CPU 频率调节器</span>
        </div>
        <div class="governor-info">
          <span class="info-label-sm">当前</span>
          <el-tag v-if="cpuGov.current" type="success" size="small" effect="dark">{{ cpuGov.current }}</el-tag>
          <span v-else class="text-muted">未知</span>
          <span v-if="cpuGov.driver" class="text-muted text-sm">· 驱动: {{ cpuGov.driver }}</span>
        </div>
        <div class="governor-buttons">
          <el-button v-for="g in cpuGov.available" :key="g"
            size="small" :type="cpuGov.current === g ? 'primary' : 'default'"
            :plain="cpuGov.current !== g"
            @click="doSetGovernor(g)" :loading="governorSetting === g">
            {{ g }}
          </el-button>
        </div>
      </div>

      <!-- I/O Scheduler -->
      <div class="section-box">
        <div class="section-header">
          <span class="section-title">I/O 调度器</span>
        </div>
        <div v-if="safeIoSched.devices.length" class="scheduler-list">
          <div v-for="d in safeIoSched.devices" :key="d.name" class="scheduler-row">
            <span class="font-mono scheduler-dev-name">{{ d.name }}</span>
            <div class="scheduler-control">
              <span class="text-muted text-sm">{{ d.current }}</span>
              <el-select
                :model-value="d.current"
                @change="onSchedulerChange(d.name, $event)"
                size="small"
                class="scheduler-select"
              >
                <el-option v-for="s in d.available" :key="s" :label="s" :value="s" />
              </el-select>
            </div>
          </div>
        </div>
        <div v-else class="text-muted text-sm">无可用块设备</div>
      </div>
    </div>

    <div class="panel-footer">
      <el-button size="small" plain @click="loadAll">刷新全部</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Check, QuestionFilled } from '@element-plus/icons-vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

interface GrubEntry { index: number; title: string; file?: string; linux?: string; initrd?: string; options?: string }
interface GrubConfig { bootloader: string; available: string[]; default: string; timeout: string; cmdline: string; entries: GrubEntry[]; config_file: string; grub_cfg_path: string; mkconfig_cmd: string }
interface CpuGov { available: string[]; current: string; driver: string }
interface IoDev { name: string; current: string; available: string[] }
interface CmdlinePreset { label: string; params: string; desc: string }

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

// GRUB
const grubCfg = ref<GrubConfig>({ bootloader: '', available: [], default: '', timeout: '', cmdline: '', entries: [], config_file: '', grub_cfg_path: '', mkconfig_cmd: '' })
const activeBootloader = ref('')

async function switchBootloader(bl: string) {
  activeBootloader.value = bl
  try {
    grubCfg.value = await systemApi.getGrubConfig(bl)
    grubDefault.value = grubCfg.value.default
    grubCmdline.value = grubCfg.value.cmdline
    loadError.value = ''
  } catch { loadError.value = `加载 ${bl} 配置失败` }
}
const grubDefault = ref('')
const grubCmdline = ref('')
const defaultSetting = ref(false)
const cmdlineSetting = ref(false)
const loadError = ref('')

// Presets
const cmdlinePresets = ref<Record<string, CmdlinePreset>>({})

// CPU
const cpuGov = ref<CpuGov>({ available: [], current: '', driver: '' })
const governorSetting = ref('')

// I/O
const ioSched = ref<{ devices: IoDev[] }>({ devices: [] })
const safeIoSched = computed(() => ({
  devices: ioSched.value.devices.map(d => {
    const available = d.available?.length ? [...d.available] : []
    if (d.current && !available.includes(d.current)) {
      available.unshift(d.current)
    }
    if (!available.length && d.current) {
      available.push(d.current)
    }
    return { ...d, available }
  })
}))

async function loadAll() {
  await Promise.all([loadGrub(), loadPresets(), loadCpu(), loadIo()])
}

async function loadGrub() {
  try {
    grubCfg.value = await systemApi.getGrubConfig()
    activeBootloader.value = grubCfg.value.bootloader
    grubDefault.value = grubCfg.value.default
    grubCmdline.value = grubCfg.value.cmdline
    loadError.value = ''
  } catch { loadError.value = '加载引导配置失败' }
}

async function loadPresets() {
  try { cmdlinePresets.value = (await systemApi.getCmdlinePresets()).presets || {} } catch { toast.error("加载引导参数预设失败") }
}

async function loadCpu() {
  try { cpuGov.value = await systemApi.getCpuGovernor() } catch { toast.error("加载 CPU 调频器信息失败") }
}

async function loadIo() {
  try { ioSched.value = await systemApi.getIoScheduler() } catch { toast.error('加载 I/O 调度器信息失败') }
}

function onEntryClick(row: GrubEntry) {
  grubDefault.value = String(row.index)
}

function selectAndSet(row: GrubEntry) {
  grubDefault.value = String(row.index)
  doSetDefault()
}

async function doSetDefault() {
  if (!(await showConfirm('设置默认启动项', `确定将默认启动项设为: ${grubDefault.value === 'saved' ? '上次启动的内核 (saved)' : grubDefault.value}？`))) return
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

function onSchedulerChange(dev: string, val: any) { doSetScheduler(dev, val) }
async function doSetScheduler(dev: string, sched: string) {
  try {
    const r = await systemApi.setIoScheduler(dev, sched)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadIo()
  } catch { toast.error('设置调度器失败') }
}

defineExpose({ loadAll })
onMounted(loadAll)
</script>

<style scoped>
.boot-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-description {
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.55;
}

/* Bootloader selector bar */
.bootloader-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.bootloader-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-0);
  flex-shrink: 0;
}

/* Section box — replaces the cramped p-3 divs */
.section-box {
  background: var(--bg-0);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-0);
}

/* Info label */
.info-label-sm {
  font-size: 12px;
  color: var(--text-2);
  flex-shrink: 0;
  min-width: 70px;
}

/* Current default row */
.current-default-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.meta-divider {
  color: var(--border);
  margin: 0 2px;
}

/* Entry section */
.entry-section {
  margin-top: 4px;
}
.entry-table {
  margin-bottom: 16px;
}
.set-default-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.entry-select {
  width: 320px;
  flex-shrink: 0;
}

/* Current cmdline */
.current-cmdline {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 16px;
}
.cmdline-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--text-0);
  background: var(--bg-2);
  padding: 4px 10px;
  border-radius: 4px;
  word-break: break-all;
}

/* Presets */
.presets-section {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
}
.preset-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}

/* Custom cmdline input */
.custom-cmdline {
  display: flex;
  gap: 12px;
  align-items: center;
}
.cmdline-input {
  flex: 1;
}

/* Two column grid */
.two-col-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
@media (max-width: 768px) {
  .two-col-grid {
    grid-template-columns: 1fr;
  }
}

/* Governor */
.governor-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.governor-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* Scheduler */
.scheduler-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}
.scheduler-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-2);
  border-radius: 4px;
}
.scheduler-dev-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-0);
}
.scheduler-control {
  display: flex;
  align-items: center;
  gap: 10px;
}
.scheduler-select {
  width: 140px;
}

/* Panel footer */
.panel-footer {
  padding-top: 4px;
}

.font-mono { font-family: 'JetBrains Mono', monospace; }
.text-muted { color: var(--text-2); }
.text-sm { font-size: 13px; }
.clickable { cursor: pointer; }
</style>
