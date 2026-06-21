<template>
  <div>
    <div class="page-title"><el-icon><Monitor /></el-icon>系统参数</div>

    <!-- System Info Descriptions -->
    <el-descriptions :column="2" border class="mb-5 system-desc">
      <el-descriptions-item label="OS">{{ info.os_name }}</el-descriptions-item>
      <el-descriptions-item label="内核">{{ info.kernel }}</el-descriptions-item>
      <el-descriptions-item label="CPU">{{ info.cpu }}</el-descriptions-item>
      <el-descriptions-item label="内存">{{ info.ram_used_gb }}/{{ info.ram_total_gb }} GB ({{ info.ram_percent }}%)</el-descriptions-item>
      <el-descriptions-item label="磁盘">{{ info.disk_used_gb }}/{{ info.disk_total_gb }} GB ({{ info.disk_percent }}%)</el-descriptions-item>
      <el-descriptions-item label="运行时间">{{ info.uptime }}</el-descriptions-item>
      <el-descriptions-item label="时区">{{ info.timezone }}</el-descriptions-item>
      <el-descriptions-item label="桌面">{{ info.desktop }}</el-descriptions-item>
    </el-descriptions>

    <!-- Collapse Panels -->
    <el-collapse v-model="activeCollapse" class="mb-5">

      <!-- Basic Config -->
      <el-collapse-item name="basic">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><EditPen /></el-icon>基础配置</span>
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
          <span class="flex items-center gap-2 font-semibold"><el-icon><Key /></el-icon>SSH 配置</span>
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
          <span class="flex items-center gap-2 font-semibold"><el-icon><Coin /></el-icon>Swap 管理</span>
        </template>
        <SwapPanel ref="swapPanelRef" />
      </el-collapse-item>

      <!-- Sysctl -->
      <el-collapse-item name="sysctl">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Setting /></el-icon>内核参数 (Sysctl)</span>
        </template>
        <div class="p-5">
          <el-input v-model="sysctlQuery" placeholder="搜索参数..." class="w-full mb-3" size="small" />
          <el-table :data="sysctlRows" size="small" stripe border height="300px">
            <el-table-column prop="key" label="参数" min-width="300">
              <template #default="scope"><span class="mono text-sm">{{ scope.row.key }}</span></template>
            </el-table-column>
            <el-table-column prop="value" label="值" min-width="200">
              <template #default="scope"><span class="mono text-sm">{{ scope.row.value }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="scope"><el-button size="small" plain @click="openEdit(scope.row.key, scope.row.value)">修改</el-button></template>
            </el-table-column>
          </el-table>
        </div>
      </el-collapse-item>

      <!-- Hosts File -->
      <el-collapse-item name="hosts">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Document /></el-icon>Hosts 文件</span>
        </template>
        <div class="p-5">
          <el-input v-model="hosts" type="textarea" :rows="12" class="w-full mb-3 font-mono" style="font-size: 12px" />
          <el-button size="small" @click="saveHosts">保存</el-button>
        </div>
      </el-collapse-item>

      <!-- NTP -->
      <el-collapse-item name="ntp">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Clock /></el-icon>NTP 时间同步</span>
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
          <span class="flex items-center gap-2 font-semibold"><el-icon><Setting /></el-icon>系统资源限制 (ulimits)</span>
        </template>
        <div class="p-5">
          <div v-if="ulimitsRunning" class="mb-4">
            <div class="font-semibold mb-2">当前运行限制:</div>
            <pre class="text-xs font-mono whitespace-pre-wrap" style="background: var(--bg-1); padding: 10px; border-radius: 6px; max-height: 200px; overflow: auto">{{ ulimitsRunning }}</pre>
          </div>
          <div class="font-semibold mb-2">/etc/security/limits.conf:</div>
          <el-input v-model="ulimitsFile" type="textarea" :rows="14" class="w-full mb-3 font-mono" style="font-size: 12px" />
          <el-button size="small" type="primary" @click="saveUlimitsConf" :loading="ulimitsSaving">保存</el-button>
          <el-button size="small" @click="loadUlimits">刷新</el-button>
        </div>
      </el-collapse-item>

      <!-- Kernel Modules -->
      <el-collapse-item name="modules">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Box /></el-icon>内核模块</span>
        </template>
        <KernelModulesPanel ref="modulesPanelRef" />
      </el-collapse-item>

      <!-- Boot & Kernel -->
      <el-collapse-item name="boot-kernel">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Cpu /></el-icon>引导 & 内核调优</span>
        </template>
        <BootKernelPanel ref="bootKernelPanelRef" />
      </el-collapse-item>

      <!-- System Optimization -->
      <el-collapse-item name="optimization">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Lightning /></el-icon>系统优化方案</span>
        </template>
        <SystemOptimizationPanel ref="optimizationPanelRef" />
      </el-collapse-item>

      <!-- User Management -->
      <el-collapse-item name="users">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><User /></el-icon>用户管理</span>
        </template>
        <UserManagementPanel ref="usersPanelRef" />
      </el-collapse-item>

      <!-- System Logs -->
      <el-collapse-item name="logs">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Tickets /></el-icon>系统日志</span>
        </template>
        <div class="p-5">
          <div class="flex gap-3 mb-3 items-center flex-wrap">
            <el-input v-model="logUnit" placeholder="服务名(可选)" style="width: 160px" size="small" />
            <el-select v-model="logPriority" placeholder="级别" style="width: 120px" size="small" clearable>
              <el-option label="emerg" value="emerg" /><el-option label="alert" value="alert" />
              <el-option label="crit" value="crit" /><el-option label="err" value="err" />
              <el-option label="warning" value="warning" /><el-option label="notice" value="notice" />
              <el-option label="info" value="info" /><el-option label="debug" value="debug" />
            </el-select>
            <el-select v-model="logLines" style="width: 100px" size="small">
              <el-option :value="50" label="50行" /><el-option :value="100" label="100行" />
              <el-option :value="200" label="200行" /><el-option :value="500" label="500行" />
            </el-select>
            <el-button size="small" @click="loadLogs">加载日志</el-button>
          </div>
          <div class="terminal">{{ logs }}</div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- System Update -->
    <div class="mb-5">
      <el-button type="warning" @click="runUpdate" :loading="updateState.running">
        <el-icon class="mr-1"><Download /></el-icon>系统更新
      </el-button>
      <div v-if="updateState.output" class="mt-3 p-3 rounded text-xs font-mono max-h-[300px] overflow-auto" style="background: var(--bg-1); border: 1px solid var(--border-1)">
        <div v-html="updateOutputHtml"></div>
      </div>
    </div>

    <!-- Sysctl Edit Dialog -->
    <el-dialog v-model="editModal" title="修改 Sysctl 参数" width="400px">
      <div class="mb-2"><strong>参数:</strong> <span class="mono">{{ editKey }}</span></div>
      <div class="mb-3"><strong>当前值:</strong> {{ editCurrent }}</div>
      <el-input v-model="editValue" placeholder="新值" class="w-full" @keyup.enter="saveEdit" />
      <template #footer>
        <el-button plain @click="editModal = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { systemApi, type SshConfig } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useSseTask } from '@/composables/useSseTask'
import { useConfirm } from '@/composables/useConfirm'
import type { SystemInfo } from '@/types/api'
import SwapPanel from '@/components/system/SwapPanel.vue'
import KernelModulesPanel from '@/components/system/KernelModulesPanel.vue'
import SystemOptimizationPanel from '@/components/system/SystemOptimizationPanel.vue'
import BootKernelPanel from '@/components/system/BootKernelPanel.vue'
import UserManagementPanel from '@/components/system/UserManagementPanel.vue'

const toast = useToast()
const { confirm: showConfirm } = useConfirm()
const { state: updateState, start: startUpdate, outputHtml: updateOutputHtml } = useSseTask()

const info = ref<SystemInfo>({} as SystemInfo)
const hostname = ref('')
const timezones = ref<string[]>([])
const tz = ref('')
const locales = ref<string[]>([])
const loc = ref('')
const sysctl = ref<Record<string, string>>({})
const sysctlQuery = ref('')
const hosts = ref('')
const editModal = ref(false)
const editKey = ref('')
const editCurrent = ref('')
const editValue = ref('')

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

// Sub-component refs
const swapPanelRef = ref<InstanceType<typeof SwapPanel>>()
const modulesPanelRef = ref<InstanceType<typeof KernelModulesPanel>>()
const optimizationPanelRef = ref<InstanceType<typeof SystemOptimizationPanel>>()
const bootKernelPanelRef = ref<InstanceType<typeof BootKernelPanel>>()
const usersPanelRef = ref<InstanceType<typeof UserManagementPanel>>()

const sysctlRows = computed(() => {
  const q = sysctlQuery.value.toLowerCase()
  return Object.entries(sysctl.value)
    .filter(([k]) => !q || k.toLowerCase().includes(q))
    .slice(0, 300)
    .map(([key, value]) => ({ key, value }))
})

async function load() {
  const [i, tzList, locList, sc, ho, sshCfg] = await Promise.all([
    systemApi.getInfo(), systemApi.getTimezones(), systemApi.getLocales(),
    systemApi.getSysctl(), systemApi.getHosts(), systemApi.getSshConfig(),
  ])
  info.value = i; timezones.value = tzList; tz.value = i.timezone
  locales.value = locList; loc.value = i.locale; sysctl.value = sc; hosts.value = ho.content
  ssh.value = sshCfg
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

async function runUpdate() {
  try {
    const r = await systemApi.update()
    if (r.task_id) startUpdate(r.task_id)
    else toast.error('Failed to start update task')
  } catch { toast.error('Failed to start update task') }
}

function openEdit(k: string, v: string) {
  editKey.value = k; editCurrent.value = v; editValue.value = v; editModal.value = true
}

async function saveEdit() {
  const r = await systemApi.setSysctl(editKey.value, editValue.value)
  toast.show(r.success ? '已设置' : '失败', r.success ? 'success' : 'error')
  editModal.value = false
  if (r.success) sysctl.value = await systemApi.getSysctl()
}

async function saveHosts() {
  const r = await systemApi.saveHosts(hosts.value)
  toast.show(r.success ? '已保存' : '失败', r.success ? 'success' : 'error')
}

// ── NTP ──
const ntpStatus = ref<{ ntp_enabled: boolean; synced: boolean; service?: string }>({ ntp_enabled: false, synced: false })
const ntpToggling = ref(false)

async function loadNtp() {
  try { ntpStatus.value = await systemApi.getNtpStatus() } catch { /* ignore */ }
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
  } catch { /* ignore */ }
}

async function saveUlimitsConf() {
  if (!(await showConfirm('保存 ulimits', '错误的配置可能影响系统运行，确定？'))) return
  ulimitsSaving.value = true
  try {
    const r = await systemApi.saveUlimits(ulimitsFile.value)
    toast.show(r.message, r.success ? 'success' : 'error')
  } finally { ulimitsSaving.value = false }
}

// ── Logs ──
const logs = ref('')
const logLines = ref(100)
const logUnit = ref('')
const logPriority = ref('')

async function loadLogs() {
  try {
    logs.value = (await systemApi.getJournalLogs(logLines.value, logUnit.value, logPriority.value)).logs || 'No logs'
  } catch { logs.value = 'Failed to load logs' }
}

onMounted(() => {
  load(); loadNtp(); loadUlimits()
  swapPanelRef.value?.load()
  modulesPanelRef.value?.load()
  bootKernelPanelRef.value?.loadAll()
  optimizationPanelRef.value?.loadProfiles()
  usersPanelRef.value?.loadUsers()
  loadLogs()
})
</script>

<style scoped>
.mono { font-family: 'JetBrains Mono', monospace; }
.system-desc :deep(.el-descriptions__label) {
  padding: 12px 16px;
  font-weight: 600;
  background: var(--bg-1);
}
.system-desc :deep(.el-descriptions__content) {
  padding: 12px 16px;
}
</style>
