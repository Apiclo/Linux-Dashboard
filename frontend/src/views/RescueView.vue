<template>
  <div>
    <div class="page-title"><el-icon><SwitchFilled /></el-icon>系统救援</div>

    <!-- ═══════════ ISO 本地源管理 ═══════════ -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <span class="flex items-center gap-2 font-semibold"><el-icon><FolderOpened /></el-icon>ISO 本地源管理</span>
      </template>

      <!-- 挂载 ISO -->
      <div class="mb-4">
        <div class="font-semibold text-sm mb-3">挂载 ISO 镜像</div>
        <div class="flex gap-3 items-center flex-wrap">
          <el-input v-model="isoPath" placeholder="ISO 文件路径 (如 /data/ubuntu-22.04.iso)" size="small" class="flex-1" style="min-width: 280px" />
          <el-input v-model="isoMountPoint" placeholder="挂载点" size="small" style="width: 160px" />
          <el-button size="small" type="primary" @click="doMountIso" :loading="isoMounting">
            <el-icon class="mr-1"><Upload /></el-icon>挂载
          </el-button>
          <el-checkbox v-model="isoConfigureRepo" size="small">配置为本地源</el-checkbox>
        </div>
      </div>

      <!-- 已挂载的 ISO -->
      <div v-if="mountedIsos.length" class="mb-4">
        <el-divider content-position="left">已挂载的 ISO</el-divider>
        <el-table :data="mountedIsos" size="small" stripe border>
          <el-table-column prop="source" label="设备/文件" min-width="200">
            <template #default="{ row }"><span class="font-mono text-sm">{{ row.source }}</span></template>
          </el-table-column>
          <el-table-column prop="target" label="挂载点" min-width="160">
            <template #default="{ row }"><span class="font-mono text-sm">{{ row.target }}</span></template>
          </el-table-column>
          <el-table-column prop="fstype" label="类型" width="100" />
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button size="small" plain @click="browseIso(row.target)">浏览内容</el-button>
              <el-button size="small" type="danger" plain @click="doUmountIso(row.target)">卸载</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 本地源状态 -->
      <div class="mb-3">
        <el-divider content-position="left">本地源状态</el-divider>
        <div class="flex gap-3 items-center">
          <el-button size="small" plain @click="loadRepoStatus">刷新状态</el-button>
          <span v-if="repoStatus.configured" class="text-sm" style="color: var(--green)">
            <el-icon><CircleCheck /></el-icon> 本地源已配置 ({{ repoStatus.config_file }})
          </span>
          <span v-else class="text-sm" style="color: var(--text-2)">本地源未配置</span>
          <el-button v-if="repoStatus.configured" size="small" type="danger" plain @click="doRemoveRepo">移除本地源</el-button>
        </div>
      </div>
    </el-card>

    <!-- ═══════════ Chroot 救援 ═══════════ -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <span class="flex items-center gap-2 font-semibold"><el-icon><Monitor /></el-icon>Chroot 救援</span>
      </template>

      <div class="mb-4">
        <div class="font-semibold text-sm mb-3">目标系统</div>
        <div class="flex gap-3 items-center flex-wrap">
          <el-input v-model="chrootRoot" placeholder="目标根路径" size="small" style="width: 200px" />
          <el-select v-model="chrootShell" size="small" style="width: 160px">
            <el-option label="/bin/bash" value="/bin/bash" />
            <el-option label="/bin/sh" value="/bin/sh" />
            <el-option label="/bin/zsh" value="/bin/zsh" />
          </el-select>
          <el-button size="small" type="primary" @click="doPrepare" :loading="preparing">准备环境</el-button>
          <el-button size="small" type="warning" @click="doTeardown" :loading="tearingDown">清理</el-button>
          <el-button size="small" plain @click="loadChrootStatus">检查状态</el-button>
        </div>
      </div>

      <!-- Chroot 状态 -->
      <div v-if="chrootStatus" class="mb-4">
        <div class="grid grid-cols-12 gap-2">
          <div v-for="(mounted, target) in chrootStatus.mounts" :key="target"
            class="col-span-6 md:col-span-4">
            <el-tag :type="mounted ? 'success' : 'info'" size="small" class="w-full text-center">
              {{ target }}: {{ mounted ? '已挂载' : '未挂载' }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- xterm.js 交互终端 -->
      <XTermTerminal
        v-if="showTerminal"
        ref="xtermRef"
        :root="chrootRoot"
        :shell="chrootShell"
        @connected="onTermConnected"
        @disconnected="onTermDisconnected"
      />
      <div v-else class="p-8 text-center" style="color: var(--text-2); background: var(--bg-0); border-radius: var(--radius-md)">
        <el-icon style="font-size: 2rem"><Monitor /></el-icon>
        <div class="mt-2">准备 chroot 环境后，点击「连接」进入交互终端</div>
      </div>
    </el-card>

    <!-- ISO 内容浏览对话框 -->
    <el-dialog v-model="browseVisible" title="ISO 内容" width="700px">
      <div v-if="browseLoading" class="text-center py-6" style="color: var(--text-2)">
        <el-icon class="is-loading" :size="20"><Loading /></el-icon> 正在读取...
      </div>
      <el-table v-else :data="browseItems" size="small" stripe border max-height="400">
        <el-table-column prop="name" label="文件名" min-width="400">
          <template #default="{ row }"><span class="font-mono text-sm">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column label="大小" width="120">
          <template #default="{ row }">
            <span v-if="row.size > 0">{{ (row.size / 1024 / 1024).toFixed(2) }} MB</span>
            <span v-else style="color: var(--text-2)">DIR</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { FolderOpened, Upload, Monitor, CircleCheck, Loading, SwitchFilled } from '@element-plus/icons-vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import XTermTerminal from '@/components/terminal/XTermTerminal.vue'

interface IsoItem { source: string; target: string; fstype: string }
interface BrowseItem { name: string; size: number }
interface RepoStatus { configured: boolean; config_file: string; pkg_manager: string }
interface ChrootStatus { root: string; exists: boolean; has_bin: boolean; mounts: Record<string, boolean>; all_ready: boolean }

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

// ── ISO 管理 ──
const isoPath = ref('/data/linux.iso')
const isoMountPoint = ref('/mnt/iso')
const isoConfigureRepo = ref(true)
const isoMounting = ref(false)
const mountedIsos = ref<IsoItem[]>([])
const repoStatus = ref<RepoStatus>({ configured: false, config_file: '', pkg_manager: '' })

// ── Chroot ──
const chrootRoot = ref('/mnt')
const chrootShell = ref('/bin/bash')
const preparing = ref(false)
const tearingDown = ref(false)
const chrootStatus = ref<ChrootStatus | null>(null)
const showTerminal = ref(true)

// ── ISO 浏览 ──
const browseVisible = ref(false)
const browseItems = ref<BrowseItem[]>([])
const browseLoading = ref(false)

// ── API 调用 ──
const rescueApi = {
  async request<T = any>(url: string, opts?: { method?: string; body?: any }): Promise<T> {
    const method = opts?.method?.toLowerCase() || 'get'
    const res = method === 'get'
      ? await fetch('/api' + url)
      : await fetch('/api' + url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(opts?.body) })
    return res.json()
  },
  mountIso: (iso_path: string, mount_point: string, configure_repo: boolean) =>
    rescueApi.request('/rescue/iso/mount', { method: 'POST', body: { iso_path, mount_point, configure_repo } }),
  umountIso: (mount_point: string) =>
    rescueApi.request('/rescue/iso/umount', { method: 'POST', body: { mount_point } }),
  getMountedIsos: () => rescueApi.request<{ isos: IsoItem[] }>('/rescue/iso/mounted'),
  listIso: (iso_path: string) =>
    rescueApi.request<{ success: boolean; items: BrowseItem[]; message: string }>('/rescue/iso/list', { method: 'POST', body: { iso_path } }),
  getRepoStatus: () => rescueApi.request<RepoStatus>('/rescue/iso/repo-status'),
  removeRepo: () => rescueApi.request('/rescue/iso/remove-repo', { method: 'POST' }),
  prepareChroot: (root: string) =>
    rescueApi.request<{ success: boolean; message: string }>('/rescue/chroot/prepare', { method: 'POST', body: { root } }),
  teardownChroot: (root: string) =>
    rescueApi.request<{ success: boolean; message: string }>('/rescue/chroot/teardown', { method: 'POST', body: { root } }),
  getChrootStatus: (root: string) =>
    rescueApi.request<ChrootStatus>(`/rescue/chroot/status?root=${encodeURIComponent(root)}`),
}

async function doMountIso() {
  if (!isoPath.value) { toast.warning('请输入 ISO 路径'); return }
  isoMounting.value = true
  try {
    const r = await rescueApi.mountIso(isoPath.value, isoMountPoint.value, isoConfigureRepo.value)
    if (r.success) {
      toast.success(r.message)
      await loadMountedIsos()
      if (r.repo_configured) toast.success('本地源已配置: ' + r.distro_family)
    } else toast.error(r.message)
  } catch { toast.error('挂载失败') }
  isoMounting.value = false
}

async function doUmountIso(mp: string) {
  if (!(await showConfirm('卸载 ISO', `确定卸载 ${mp}？将同时移除本地源配置。`))) return
  try {
    const r = await rescueApi.umountIso(mp)
    toast.show(r.message, r.success ? 'success' : 'error')
    await loadMountedIsos(); await loadRepoStatus()
  } catch { toast.error('卸载失败') }
}

async function loadMountedIsos() {
  try { mountedIsos.value = (await rescueApi.getMountedIsos()).isos || [] } catch { /* ignore */ }
}

async function loadRepoStatus() {
  try { repoStatus.value = await rescueApi.getRepoStatus() } catch { /* ignore */ }
}

async function doRemoveRepo() {
  if (!(await showConfirm('移除本地源', '确定移除本地源配置？'))) return
  try {
    const r = await rescueApi.removeRepo()
    toast.show(r.message, r.success ? 'success' : 'error')
    await loadRepoStatus()
  } catch { toast.error('操作失败') }
}

async function browseIso(mp: string) {
  browseVisible.value = true; browseLoading.value = true
  try {
    const r = await rescueApi.listIso(mp)
    browseItems.value = r.items || []
  } catch { /* ignore */ }
  browseLoading.value = false
}

// ── Chroot ──
async function doPrepare() {
  preparing.value = true
  try {
    const r = await rescueApi.prepareChroot(chrootRoot.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    await loadChrootStatus()
  } catch { toast.error('准备失败') }
  preparing.value = false
}

async function doTeardown() {
  tearingDown.value = true
  try {
    const r = await rescueApi.teardownChroot(chrootRoot.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    await loadChrootStatus()
  } catch { toast.error('清理失败') }
  tearingDown.value = false
}

async function loadChrootStatus() {
  try { chrootStatus.value = await rescueApi.getChrootStatus(chrootRoot.value) } catch { /* ignore */ }
}

function onTermConnected() { /* */ }
function onTermDisconnected() { /* */ }

onMounted(() => { loadMountedIsos(); loadRepoStatus(); loadChrootStatus() })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
