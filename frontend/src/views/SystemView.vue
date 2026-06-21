<template>
  <div>
    <div class="page-title">
      <el-icon><Monitor /></el-icon>系统参数
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新 (30s)" />
    </div>

    <FeatureStatus :features="sysFeatures" />

    <!-- System Info -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="font-semibold">系统信息</span>
          <el-button size="small" plain @click="copySystemInfo" :icon="CopyDocument" :disabled="!info.os_name">复制信息</el-button>
        </div>
      </template>
      <div v-if="infoLoading" class="panel-loading"><el-icon class="is-loading"><Loading /></el-icon> 加载系统信息...</div>
      <div v-if="infoError" class="panel-error">{{ infoError }}</div>
      <el-descriptions v-if="!infoLoading && !infoError" :column="2" border class="system-desc">
        <el-descriptions-item label="OS">{{ info.os_name }}</el-descriptions-item>
        <el-descriptions-item label="内核">{{ info.kernel }}</el-descriptions-item>
        <el-descriptions-item label="CPU">{{ info.cpu }}</el-descriptions-item>
        <el-descriptions-item label="内存">{{ info.ram_used_gb }}/{{ info.ram_total_gb }} GB ({{ info.ram_percent }}%)</el-descriptions-item>
        <el-descriptions-item label="磁盘">{{ info.disk_used_gb }}/{{ info.disk_total_gb }} GB ({{ info.disk_percent }}%)</el-descriptions-item>
        <el-descriptions-item label="运行时间">{{ info.uptime }}</el-descriptions-item>
        <el-descriptions-item label="时区">{{ info.timezone }}</el-descriptions-item>
        <el-descriptions-item label="桌面">{{ info.desktop }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Collapse Panels -->
    <el-collapse v-model="activeCollapse" class="mb-6">

      <!-- Basic Config -->
      <el-collapse-item name="basic">
        <template #title>
          <span class="flex items-center gap-3 font-semibold"><el-icon><EditPen /></el-icon>基础配置</span>
        </template>
        <el-form label-width="80px" size="small" class="p-5">
          <div class="flex flex-wrap gap-4">
            <div class="flex-1 min-w-[200px]">
              <el-form-item label="主机名">
                <div class="flex gap-3 w-full">
                  <el-input v-model="hostname" :placeholder="'当前: ' + info.hostname" class="flex-1" @keyup.enter="setHostname" size="small" />
                  <el-button size="small" @click="setHostname">应用</el-button>
                </div>
              </el-form-item>
            </div>
            <div class="flex-1 min-w-[200px]">
              <el-form-item label="时区">
                <div class="flex gap-3 w-full">
                  <el-select v-model="tz" filterable class="flex-1" size="small">
                    <el-option v-for="item in timezones" :key="item" :label="item" :value="item" />
                  </el-select>
                  <el-button size="small" @click="setTimezone">应用</el-button>
                </div>
              </el-form-item>
            </div>
            <div class="flex-1 min-w-[200px]">
              <el-form-item label="语言">
                <div class="flex gap-3 w-full">
                  <el-select v-model="loc" filterable class="flex-1" size="small">
                    <el-option v-for="item in locales" :key="item" :label="item" :value="item" />
                  </el-select>
                  <el-button size="small" @click="setLocale">应用</el-button>
                </div>
              </el-form-item>
            </div>
          </div>
        </el-form>
      </el-collapse-item>

      <!-- SSH Config -->
      <el-collapse-item name="ssh">
        <template #title>
          <span class="flex items-center gap-3 font-semibold"><el-icon><Key /></el-icon>SSH 配置</span>
        </template>
        <div class="p-5">
          <el-form label-width="160px" size="small">
            <el-form-item label="端口 (Port)">
              <el-input v-model="ssh.port" style="width: 100%; max-width: 160px" />
            </el-form-item>
            <el-form-item label="允许 Root 登录">
              <el-select v-model="ssh.permit_root_login" style="width: 160px">
                <el-option label="yes" value="yes" />
                <el-option label="no" value="no" />
                <el-option label="prohibit-password" value="prohibit-password" />
                <el-option label="forced-commands-only" value="forced-commands-only" />
              </el-select>
            </el-form-item>
            <el-form-item label="密码认证">
              <el-switch v-model="sshPasswordAuth" active-text="是" inactive-text="否" />
            </el-form-item>
            <el-form-item label="公钥认证">
              <el-switch v-model="sshPubkeyAuth" active-text="是" inactive-text="否" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSsh" :loading="sshSaving">保存 SSH 配置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-collapse-item>

      <!-- Swap Management -->
      <el-collapse-item name="swap">
        <template #title>
          <span class="flex items-center gap-3 font-semibold"><el-icon><Coin /></el-icon>Swap 管理</span>
        </template>
        <SwapPanel />
      </el-collapse-item>

      <!-- NTP -->
      <el-collapse-item name="ntp">
        <template #title>
          <span class="flex items-center gap-3 font-semibold"><el-icon><Clock /></el-icon>NTP 时间同步</span>
        </template>
        <div class="p-5">
          <div class="flex flex-wrap gap-6 mb-4">
            <div><strong>NTP:</strong> <el-tag :type="ntpStatus.ntp_enabled ? 'success' : 'info'" size="small">{{ ntpStatus.ntp_enabled ? '已启用' : '未启用' }}</el-tag></div>
            <div><strong>同步:</strong> <el-tag :type="ntpStatus.synced ? 'success' : 'warning'" size="small">{{ ntpStatus.synced ? '已同步' : '未同步' }}</el-tag></div>
            <div v-if="ntpStatus.service"><strong>服务:</strong> <span class="font-mono">{{ ntpStatus.service }}</span></div>
          </div>
          <div class="flex gap-3 items-center">
            <el-button size="small" type="primary" @click="toggleNtp(true)" :loading="ntpToggling">启用 NTP</el-button>
            <el-button size="small" type="danger" @click="toggleNtp(false)" :loading="ntpToggling">禁用 NTP</el-button>
            <el-button size="small" @click="loadNtp">刷新</el-button>
          </div>
        </div>
      </el-collapse-item>

      <!-- Ulimits -->
      <el-collapse-item name="ulimits">
        <template #title>
          <span class="flex items-center gap-3 font-semibold"><el-icon><Setting /></el-icon>系统资源限制 (ulimits)</span>
        </template>
        <div class="p-5">
          <div v-if="ulimitsRunning" class="mb-4">
            <div class="font-semibold mb-2">当前运行限制:</div>
            <pre class="text-sm font-mono whitespace-pre-wrap" style="background: var(--bg-1); padding: 12px; border-radius: 6px; max-height: 200px; overflow: auto">{{ ulimitsRunning }}</pre>
          </div>
          <div class="font-semibold mb-2">/etc/security/limits.conf:</div>
          <el-input v-model="ulimitsFile" type="textarea" :rows="14" class="w-full mb-3 font-mono mono-textarea" />
          <el-button size="small" type="primary" @click="saveUlimitsConf" :loading="ulimitsSaving">保存</el-button>
          <el-button size="small" @click="loadUlimits">刷新</el-button>
        </div>
      </el-collapse-item>

      <!-- Hosts File -->
      <el-collapse-item name="hosts">
        <template #title>
          <span class="flex items-center gap-3 font-semibold"><el-icon><Document /></el-icon>Hosts 文件</span>
        </template>
        <div class="p-5">
          <el-input v-model="hosts" type="textarea" :rows="12" class="w-full mb-3 font-mono mono-textarea" />
          <el-button size="small" @click="saveHosts">保存</el-button>
        </div>
      </el-collapse-item>

    </el-collapse>

    <!-- System Update -->
    <div class="mb-6">
      <el-button type="warning" @click="runUpdate" :loading="updateState.running">
        <el-icon class="mr-1"><Download /></el-icon>系统更新
      </el-button>
      <div v-if="updateState.output" class="mt-4 p-4 rounded text-sm font-mono max-h-[300px] overflow-auto" style="background: var(--bg-1); border: 1px solid var(--border)">
        <div v-html="updateOutputHtml"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { systemApi, type SshConfig } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useSseTask } from '@/composables/useSseTask'
import { useConfirm } from '@/composables/useConfirm'
import type { SystemInfo } from '@/types/api'
import SwapPanel from '@/components/system/SwapPanel.vue'
import FeatureStatus from '@/components/common/FeatureStatus.vue'

const toast = useToast()
const { confirm: showConfirm } = useConfirm()
const { state: updateState, start: startUpdate, outputHtml: updateOutputHtml } = useSseTask()

const info = ref<SystemInfo>({} as SystemInfo)
const features = ref<Record<string, any>>({})
const sysFeatures = ref<Array<{ name: string; available: boolean }>>([])
async function fetchFeatures() {
  try {
    const f = await systemApi.getFeatures()
    features.value = f
    sysFeatures.value = Object.entries(f).map(([k, v]) => ({ name: k, available: !!v }))
  } catch { /* non-critical */ }
}
const infoLoading = ref(true)
const infoError = ref('')
const hostname = ref('')
const timezones = ref<string[]>([])
const tz = ref('')
const locales = ref<string[]>([])
const loc = ref('')
const hosts = ref('')

const activeCollapse = ref(['basic', 'ssh'])

// SSH
const ssh = ref<SshConfig>({ port: '22', permit_root_login: 'yes', password_auth: 'yes', pubkey_auth: 'yes' })
const sshSaving = ref(false)
const sshPasswordAuth = computed({
  get: () => ssh.value.password_auth === 'yes',
  set: (v: boolean) => { ssh.value.password_auth = v ? 'yes' : 'no' },
})
const sshPubkeyAuth = computed({
  get: () => ssh.value.pubkey_auth === 'yes',
  set: (v: boolean) => { ssh.value.pubkey_auth = v ? 'yes' : 'no' },
})

function copySystemInfo() {
  const i = info.value
  const text = `OS: ${i.os_name}\n内核: ${i.kernel}\nCPU: ${i.cpu}\n` +
    `内存: ${i.ram_used_gb}/${i.ram_total_gb} GB (${i.ram_percent}%)\n` +
    `磁盘: ${i.disk_used_gb}/${i.disk_total_gb} GB (${i.disk_percent}%)\n` +
    `运行时间: ${i.uptime}\n时区: ${i.timezone}\n桌面: ${i.desktop}`
  navigator.clipboard.writeText(text).then(() => toast.success('已复制')).catch(() => toast.error('复制失败'))
}

async function load() {
  infoLoading.value = true
  infoError.value = ''
  try {
    const [i, tzList, locList, ho, sshCfg] = await Promise.all([
      systemApi.getInfo(), systemApi.getTimezones(), systemApi.getLocales(),
      systemApi.getHosts(), systemApi.getSshConfig(),
    ])
    info.value = i; timezones.value = tzList; tz.value = i.timezone
    locales.value = locList; loc.value = i.locale; hosts.value = ho.content
    ssh.value = sshCfg
  } catch (e: any) {
    infoError.value = e?.message || '系统信息加载失败，请刷新重试'
  } finally {
    infoLoading.value = false
  }
}

async function setHostname() {
  const r = await systemApi.setHostname(hostname.value)
  toast.show(r.message || (r.success ? '已设置' : '失败'), r.success ? 'success' : 'error')
  if (r.success) load()
}

async function setTimezone() {
  const r = await systemApi.setTimezone(tz.value)
  toast.show(r.message || '已设置', r.success ? 'success' : 'error')
}

async function setLocale() {
  const r = await systemApi.setLocale(loc.value)
  toast.show(r.message || '已设置', r.success ? 'success' : 'error')
}

async function saveSsh() {
  sshSaving.value = true
  try {
    const r = await systemApi.saveSshConfig(ssh.value)
    toast.show(r.message || (r.success ? '已保存' : '失败'), r.success ? 'success' : 'error')
    if (r.success) ssh.value = await systemApi.getSshConfig()
  } finally { sshSaving.value = false }
}

async function saveHosts() {
  const r = await systemApi.saveHosts(hosts.value)
  toast.show(r.success ? '已保存' : '失败', r.success ? 'success' : 'error')
}

async function runUpdate() {
  try {
    const r = await systemApi.update()
    if (r.task_id) startUpdate(r.task_id)
    else toast.error('Failed to start update task')
  } catch { toast.error('Failed to start update task') }
}

// ── NTP ──
const ntpStatus = ref<{ ntp_enabled: boolean; synced: boolean; service?: string }>({ ntp_enabled: false, synced: false })
const ntpToggling = ref(false)

async function loadNtp() {
  try { ntpStatus.value = await systemApi.getNtpStatus() } catch { toast.error('加载失败') }
}

async function toggleNtp(enable: boolean) {
  ntpToggling.value = true
  try {
    const r = await systemApi.toggleNtp(enable)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadNtp()
  } finally { ntpToggling.value = false }
}

// ── Ulimits ──
const ulimitsFile = ref('')
const ulimitsRunning = ref('')
const ulimitsSaving = ref(false)

async function loadUlimits() {
  try {
    const r = await systemApi.getUlimits()
    ulimitsFile.value = r.file; ulimitsRunning.value = r.running
  } catch { toast.error('加载失败') }
}

async function saveUlimitsConf() {
  if (!(await showConfirm('保存 ulimits', '错误的配置可能影响系统运行，确定？'))) return
  ulimitsSaving.value = true
  try {
    const r = await systemApi.saveUlimits(ulimitsFile.value)
    toast.show(r.message, r.success ? 'success' : 'error')
  } finally { ulimitsSaving.value = false }
}

// Auto-refresh
const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(() => { load(); loadNtp(); loadUlimits() }, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}

onMounted(() => {
  load(); loadNtp(); loadUlimits(); fetchFeatures()
})
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>

<style scoped>
.mono { font-family: 'JetBrains Mono', monospace; }
.mono-textarea :deep(textarea) { font-family: 'JetBrains Mono', monospace !important; }
.font-mono { font-family: 'JetBrains Mono', monospace; }
.system-desc :deep(.el-descriptions__label) {
  padding: 14px 18px;
  font-weight: 600;
  background: var(--bg-1);
  font-size: 14px;
}
.system-desc :deep(.el-descriptions__content) {
  padding: 14px 18px;
  font-size: 14px;
}
</style>
