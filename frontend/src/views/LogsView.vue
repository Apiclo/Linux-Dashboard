<template>
  <div>
    <div class="page-title">
      <el-icon><Tickets /></el-icon>日志与安全
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新 (30s)" />
    </div>

    <FeatureStatus :features="features" />

    <!-- Journal Logs -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Tickets /></el-icon>系统日志</span>
          <el-button size="small" plain @click="downloadLogs"><el-icon><Download /></el-icon>下载诊断报告</el-button>
        </div>
      </template>
      <div class="flex gap-3 mb-4 items-center flex-wrap">
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
    </el-card>

    <!-- System Logs & Security Tabs -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Lock /></el-icon>日志与安全</span>
      </template>
      <el-tabs v-model="logTab">
        <!-- dmesg -->
        <el-tab-pane name="dmesg">
          <template #label>dmesg</template>
          <div class="flex gap-3 mb-4 items-center">
            <el-select v-model="dmesgLevel" size="small" class="w-32" clearable placeholder="级别">
              <el-option v-for="l in ['emerg','alert','crit','err','warn','notice','info','debug']" :key="l" :label="l" :value="l" />
            </el-select>
            <el-select v-model="dmesgLines" size="small" class="w-28">
              <el-option v-for="n in [100,200,500,1000,2000]" :key="n" :label="n+'行'" :value="n" />
            </el-select>
            <el-button size="small" @click="loadDmesg">加载</el-button>
          </div>
          <div class="terminal" style="min-height:180px;max-height:350px">{{ dmesgLogs }}</div>
        </el-tab-pane>

        <!-- auditd -->
        <el-tab-pane name="audit">
          <template #label>auditd</template>
          <el-alert v-if="!features.find(f => f.name === 'auditd')?.available" type="warning" :closable="false" show-icon class="mb-4">
            auditd 未启用，该系统未配置审计守护进程
          </el-alert>
          <el-button v-else size="small" class="mb-4" @click="loadAudit">加载审计日志</el-button>
          <div class="terminal" style="min-height:180px;max-height:350px">{{ auditLogs }}</div>
        </el-tab-pane>

        <!-- Cron Editor -->
        <el-tab-pane name="cron">
          <template #label>Cron</template>
          <div class="flex gap-3 mb-4 items-center">
            <el-input v-model="cronUser" placeholder="用户(可选)" size="small" style="width:120px" />
            <el-button size="small" @click="loadCron">加载</el-button>
          </div>
          <el-input v-model="cronContent" type="textarea" :rows="10" class="w-full mb-4 mono-textarea" />
          <el-button size="small" type="primary" @click="saveCron">保存</el-button>
        </el-tab-pane>

        <!-- SELinux/AppArmor -->
        <el-tab-pane name="mac">
          <template #label>SELinux/AppArmor</template>
          <el-button size="small" plain class="mb-4" @click="loadMac">刷新</el-button>
          <div v-if="mac.selinux?.installed" class="mb-4 p-4 rounded-lg" style="background:var(--bg-0)">
            <div class="font-semibold text-sm mb-2">SELinux</div>
            <div class="mb-2">
              模式: <el-tag :type="mac.selinux?.mode==='Enforcing'?'success':mac.selinux?.mode==='Permissive'?'warning':'info'" size="small">{{ mac.selinux?.mode || '未知' }}</el-tag>
              · 策略: {{ mac.selinux?.policy || '—' }}
            </div>
            <div class="flex gap-3 mt-3">
              <el-button size="small" @click="doSetSelinux('enforcing')">Enforcing</el-button>
              <el-button size="small" @click="doSetSelinux('permissive')">Permissive</el-button>
            </div>
          </div>
          <div v-if="mac.apparmor?.installed" class="p-4 rounded-lg" style="background:var(--bg-0)">
            <div class="font-semibold text-sm mb-2">AppArmor</div>
            <div>已加载 {{ mac.apparmor?.profiles_loaded || 0 }} 个配置 ({{ mac.apparmor?.profiles_enforce || 0 }} enforce)</div>
          </div>
          <div v-if="!mac.selinux?.installed && !mac.apparmor?.installed" class="text-sm" style="color:var(--text-2)">未检测到 SELinux 或 AppArmor</div>
        </el-tab-pane>

        <!-- Timer & Cron -->
        <el-tab-pane name="timers">
          <template #label>定时任务</template>
          <el-tabs v-model="timerTab">
            <el-tab-pane name="systemd">
              <template #label>systemd Timers</template>
              <el-button size="small" class="mb-4" @click="loadTimers">刷新</el-button>
              <el-table v-if="timerData.timers?.length" :data="timerData.timers" size="small" stripe border max-height="350">
                <el-table-column prop="next" label="下次" width="150" />
                <el-table-column prop="left" label="剩余" width="90" />
                <el-table-column prop="unit" label="Timer" min-width="220">
                  <template #default="{ row }"><span class="font-mono text-sm">{{ row.unit }}</span></template>
                </el-table-column>
                <el-table-column prop="activates" label="激活" min-width="180">
                  <template #default="{ row }"><span class="font-mono text-sm">{{ row.activates }}</span></template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="无 systemd timers" :image-size="40" />
            </el-tab-pane>
            <el-tab-pane name="crontab">
              <template #label>Crontab</template>
              <el-button size="small" class="mb-4" @click="loadCrontab">刷新</el-button>
              <div v-if="cronParsed.entries?.length" class="text-sm">
                <div v-for="(e,i) in cronParsed.entries.slice(0,40)" :key="i" class="py-2 px-3 mb-2 rounded font-mono flex gap-3" style="background:var(--bg-2)">
                  <span style="color:var(--accent)">{{ e.minute }} {{ e.hour }} {{ e.day }} {{ e.month }} {{ e.weekday }}</span>
                  <span style="color:var(--text-1)">{{ e.command }}</span>
                </div>
              </div>
              <div v-else class="text-sm" style="color:var(--text-2)">无 crontab 条目</div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { Tickets, Download, Lock } from '@element-plus/icons-vue'

const toast = useToast()

// Features
const features = ref<Array<{ name: string; available: boolean }>>([])
async function fetchFeatures() {
  try {
    const f = await systemApi.getFeatures()
    features.value = Object.entries(f).map(([k, v]) => ({ name: k, available: !!v }))
  } catch { /* non-critical */ }
}

// ── Journal Logs ──
const logs = ref('')
const logLines = ref(100)
const logUnit = ref('')
const logPriority = ref('')

async function loadLogs() {
  try { logs.value = (await systemApi.getJournalLogs(logLines.value, logUnit.value, logPriority.value)).logs || 'No logs' } catch { logs.value = 'Failed to load logs' }
}

// ── dmesg ──
const dmesgLogs = ref('')
const dmesgLevel = ref('')
const dmesgLines = ref(200)
async function loadDmesg() { try { dmesgLogs.value = (await systemApi.getDmesg(dmesgLines.value, dmesgLevel.value)).logs } catch {} }

// ── auditd ──
const auditLogs = ref('')
async function loadAudit() { try { auditLogs.value = (await systemApi.getAuditLogs()).logs } catch {} }

// ── Diagnostic ──
async function downloadLogs() {
  try {
    const r = await systemApi.getDiagnostic()
    const blob = new Blob([r.report], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `diagnostic-${Date.now()}.md`; a.click()
    URL.revokeObjectURL(url); toast.success('已下载')
  } catch { toast.error('下载失败') }
}

// ── Cron Editor ──
const cronContent = ref('')
const cronUser = ref('')
async function loadCron() { try { const r = await systemApi.getCrontab(cronUser.value); cronContent.value = r.content } catch {} }
async function saveCron() { try { const r = await systemApi.setCrontab(cronContent.value, cronUser.value); toast.show(r.message, r.success ? 'success' : 'error') } catch { toast.error('保存失败') } }

// ── SELinux/AppArmor ──
const mac = ref<Record<string, any>>({})
async function loadMac() { try { mac.value = await systemApi.getMacStatus() } catch {} }
async function doSetSelinux(mode: string) {
  try { const r = await systemApi.setSelinux(mode); toast.show(r.message, r.success ? 'success' : 'error'); if (r.success) await loadMac() } catch { toast.error('操作失败') }
}

// ── Timers & Cron ──
const timerTab = ref('systemd')
const timerData = ref<{ timers: any[] }>({ timers: [] })
const cronParsed = ref<{ entries: any[] }>({ entries: [] })
async function loadTimers() { try { timerData.value = await systemApi.getTimers() } catch {} }
async function loadCrontab() { try { cronParsed.value = await systemApi.getCrontabParsed() } catch {} }

const logTab = ref('dmesg')

// Auto-refresh
const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(() => { loadLogs(); loadTimers() }, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}

onMounted(() => { fetchFeatures(); loadLogs(); loadTimers() })
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>

<style scoped>
.mono-textarea :deep(textarea) { font-family: 'JetBrains Mono', monospace !important; }
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
