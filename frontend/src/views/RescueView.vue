<template>
  <div>
    <div class="page-title"><el-icon><SwitchFilled /></el-icon>系统救援</div>

    <FeatureStatus :features="features" />

    <!-- ═══════════ ISO 本地源管理 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><FolderOpened /></el-icon>ISO 本地源管理</span>
      </template>

      <!-- 挂载 ISO -->
      <div class="mb-4">
        <div class="font-semibold text-sm mb-3">挂载 ISO 镜像</div>
        <div class="flex gap-4 items-center flex-wrap">
          <el-input v-model="isoPath" placeholder="ISO 文件路径 (如 /data/ubuntu-22.04.iso)" size="small" class="flex-1" style="min-width: 280px" />
          <el-button size="small" plain @click="openFileBrowser(isoPath)">浏览</el-button>
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
        <div class="flex gap-4 items-center">
          <el-button size="small" plain @click="loadRepoStatus">刷新状态</el-button>
          <span v-if="repoStatus.configured" class="text-sm" style="color: var(--green)">
            <el-icon><CircleCheck /></el-icon> 本地源已配置 ({{ repoStatus.config_file }})
          </span>
          <span v-else class="text-sm" style="color: var(--text-2)">本地源未配置</span>
          <el-button v-if="repoStatus.configured" size="small" type="danger" plain @click="doRemoveRepo">移除本地源</el-button>
        </div>
      </div>
    </el-card>

    <!-- ═══════════ SFTP 远程挂载 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex justify-between items-center">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Connection /></el-icon>SFTP 远程挂载</span>
          <el-tag v-if="!sshfsAvailable" type="warning" size="small">sshfs 未安装</el-tag>
        </div>
      </template>

      <div class="mb-4">
        <div class="font-semibold text-sm mb-3">挂载远程目录</div>
        <div class="grid grid-cols-12 gap-4">
          <div class="col-span-12 md:col-span-3">
            <el-input v-model="sftpUser" placeholder="用户名" size="small">
              <template #prepend>user@</template>
            </el-input>
          </div>
          <div class="col-span-12 md:col-span-3">
            <el-input v-model="sftpHost" placeholder="主机地址" size="small" />
          </div>
          <div class="col-span-12 md:col-span-1">
            <el-input v-model="sftpPort" placeholder="22" size="small" />
          </div>
          <div class="col-span-12 md:col-span-3">
            <el-input v-model="sftpRemotePath" placeholder="/remote/path" size="small" />
          </div>
          <div class="col-span-12 md:col-span-2">
            <el-input v-model="sftpMountPoint" placeholder="/mnt/sftp" size="small" />
          </div>
        </div>
        <div class="flex gap-4 items-center mt-3">
          <el-input v-model="sftpKeyFile" placeholder="SSH密钥路径(可选)" size="small" style="width:200px" />
          <el-checkbox v-model="sftpReconnect" size="small">自动重连</el-checkbox>
          <el-button size="small" type="primary" @click="doSftpMount" :loading="sftpMounting" :disabled="!sshfsAvailable">
            <el-icon class="mr-1"><Connection /></el-icon>挂载
          </el-button>
        </div>
      </div>

      <!-- 已挂载 -->
      <div v-if="sftpMounts.length">
        <el-divider content-position="left">已挂载的 SFTP</el-divider>
        <el-table :data="sftpMounts" size="small" stripe border>
          <el-table-column label="远程" min-width="200">
            <template #default="{ row }"><span class="font-mono text-sm">{{ row.source_full }}</span></template>
          </el-table-column>
          <el-table-column prop="target" label="挂载点" min-width="140">
            <template #default="{ row }"><span class="font-mono text-sm">{{ row.target }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button size="small" type="danger" plain @click="doSftpUmount(row.target)">卸载</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- ═══════════ Chroot 救援 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Monitor /></el-icon>Chroot 救援</span>
          <el-tooltip content="交互终端需要 pip install flask-sock。无此依赖时 chroot 准备和命令执行仍可用。" placement="top">
            <el-tag v-if="!wsAvailable" type="warning" size="small">交互终端不可用</el-tag>
          </el-tooltip>
        </div>
      </template>

      <div class="mb-4">
        <div class="font-semibold text-sm mb-3">目标系统</div>
        <div class="flex gap-4 items-center flex-wrap">
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
        <div class="mt-3">准备 chroot 环境后，点击「连接」进入交互终端</div>
      </div>
    </el-card>

    <!-- ═══════════ 引导修复 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header><span class="flex items-center gap-3 font-semibold"><el-icon><Setting /></el-icon>引导 & 内核修复</span></template>
      <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12 md:col-span-6">
          <div class="font-semibold text-sm mb-2">Grub 修复</div>
          <div class="flex gap-3 items-center flex-wrap">
            <el-input v-model="grubDisk" placeholder="目标磁盘 (如 /dev/sda)" size="small" style="width:160px" />
            <el-input v-model="grubRoot" placeholder="Chroot 根路径 (可选)" size="small" style="width:160px" />
            <el-button size="small" type="primary" @click="doGrubRepair">修复 Grub</el-button>
          </div>
        </div>
        <div class="col-span-12 md:col-span-6">
          <div class="font-semibold text-sm mb-2">initramfs 重建</div>
          <div class="flex gap-3 items-center">
            <el-checkbox v-model="initramfsAll" size="small">所有内核</el-checkbox>
            <el-button size="small" type="warning" @click="doInitramfsRebuild" :disabled="taskRebuild.running">重建</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- ═══════════ 系统快照备份 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><FolderChecked /></el-icon>系统快照备份</span>
          <el-button size="small" plain @click="loadBackups"><el-icon><Refresh /></el-icon></el-button>
        </div>
      </template>
      <div class="grid grid-cols-12 gap-4 mb-4">
        <div class="col-span-12 md:col-span-6">
          <div class="p-4 rounded-lg" style="background: var(--bg-0); border: 1px solid var(--border)">
            <div class="font-semibold text-sm mb-2">创建快照</div>
            <div class="flex gap-3 items-center flex-wrap">
              <el-input v-model="backupName" placeholder="快照名称 (可选)" size="small" style="width:160px" @keyup.enter="doCreateBackup" />
              <el-checkbox v-model="backupIncludeHome" size="small">含 /home</el-checkbox>
              <el-button size="small" type="primary" @click="doCreateBackup" :loading="backupCreating">创建</el-button>
            </div>
            <div v-if="backupResult" class="mt-2 text-xs" :style="{color: backupResult.success ? 'var(--green)' : 'var(--red)'}">
              {{ backupResult.success ? `✅ ${backupResult.name}: ${backupResult.file_count} 个文件` : '创建失败' }}
              <span v-if="backupResult.errors?.length" style="color: var(--yellow)">({{ backupResult.errors.length }} 警告)</span>
            </div>
          </div>
        </div>
        <div class="col-span-12 md:col-span-6">
          <div v-if="backups.length" class="text-xs" style="max-height: 180px; overflow-y: auto">
            <div v-for="snap in backups" :key="snap.name"
              class="flex items-center justify-between py-2 px-2 mb-1 rounded"
              style="background: var(--bg-2); border: 1px solid var(--border)">
              <div class="flex-1 min-w-0">
                <div class="font-semibold text-sm truncate">{{ snap.name }}</div>
                <div style="color: var(--text-2)">{{ snap.created }} · {{ snap.file_count }} 文件
                  <el-tag v-if="snap.include_home" size="small" type="warning" class="ml-1">含/home</el-tag>
                </div>
              </div>
              <div class="flex gap-1 flex-shrink-0">
                <el-button size="small" text @click="doCompareBackup(snap.name)" :disabled="backupComparing === snap.name">比较</el-button>
                <el-button size="small" text type="danger" @click="doDeleteBackup(snap.name)">删除</el-button>
              </div>
            </div>
          </div>
          <div v-else class="text-xs text-center py-8" style="color: var(--text-2)">暂无快照，创建第一个系统备份</div>
        </div>
      </div>
      <!-- 比较结果 -->
      <div v-if="compareResult?.diffs?.length" class="p-4 rounded-lg" style="background: var(--bg-0)">
        <div class="font-semibold text-sm mb-2">快照比较: {{ compareResult.name }}</div>
        <div v-for="(d, i) in compareResult.diffs" :key="i" class="flex gap-2 text-xs py-1" style="border-bottom: 1px solid var(--border)">
          <span class="font-mono" style="color: var(--text-2)">{{ d.file }}</span>
          <el-tag :type="d.status === 'changed' ? 'warning' : d.status === 'deleted' ? 'danger' : 'info'" size="small">{{ d.status }}</el-tag>
        </div>
      </div>
    </el-card>

    <!-- 文件浏览器弹窗 -->
    <el-dialog v-model="fileBrowserVisible" title="文件浏览" width="650px">
      <div class="flex gap-3 mb-4 items-center">
        <el-input v-model="browsePath" size="small" class="flex-1" @keyup.enter="navigateTo(browsePath)" />
        <el-button size="small" @click="navigateTo(browsePath)">跳转</el-button>
        <el-button size="small" plain @click="navigateTo('/')">根目录</el-button>
      </div>
      <el-table :data="dirItems" size="small" stripe border max-height="350" @row-click="onBrowseClick">
        <el-table-column label="名称" min-width="300">
          <template #default="{row}"><span class="font-mono text-sm">{{row.is_dir?'📁':'📄'}} {{row.name}}</span></template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{row}">{{row.is_dir?'—':(row.size/1024/1024).toFixed(1)+'M'}}</template>
        </el-table-column>
      </el-table>
      <template #footer><el-button @click="fileBrowserVisible=false">取消</el-button><el-button type="primary" @click="selectBrowsePath">选择此目录</el-button></template>
    </el-dialog>

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
import { systemApi } from '@/api/system'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { FolderOpened, Upload, Monitor, CircleCheck, Loading, SwitchFilled, Connection } from '@element-plus/icons-vue'
import { rescueApi } from '@/api/rescue'
import type { ChrootStatus } from '@/types/api'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useSseTask } from '@/composables/useSseTask'
import XTermTerminal from '@/components/terminal/XTermTerminal.vue'

interface IsoItem { source: string; target: string; fstype: string }
interface BrowseItem { name: string; size: number }
interface RepoStatus { configured: boolean; config_file: string; pkg_manager: string }

const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['sshfs','isoinfo','sudo','chroot'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }
const { confirm: showConfirm } = useConfirm()

// ── SFTP ──
const sftpUser = ref('root'); const sftpHost = ref(''); const sftpPort = ref('22')
const sftpRemotePath = ref('/'); const sftpMountPoint = ref('/mnt/sftp')
const sftpReconnect = ref(true); const sftpKeyFile = ref('')
const sftpMounting = ref(false); const sftpMounts = ref<IsoItem[]>([]); const sshfsAvailable = ref(true)

async function checkSshfs() { try { const r = await rescueApi.checkSshfs(); sshfsAvailable.value = r.available } catch { sshfsAvailable.value = false } }
async function doSftpMount() {
  if (!sftpHost.value) { toast.warning('请输入主机地址'); return }
  sftpMounting.value = true
  try { const r = await rescueApi.mountSftp(sftpUser.value, sftpHost.value, parseInt(sftpPort.value)||22, sftpRemotePath.value, sftpMountPoint.value, `${sftpReconnect.value?'reconnect,ServerAliveInterval=15,StrictHostKeyChecking=no':''}${sftpKeyFile.value?',IdentityFile='+sftpKeyFile.value:''}`); if(r.success){ toast.success('SFTP 已挂载'); await loadSftpMounts() } else toast.error(r.message) } catch { toast.error('挂载失败') }
  sftpMounting.value = false
}
async function doSftpUmount(mp: string) { try { const r = await rescueApi.umountSftp(mp); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadSftpMounts() } catch { toast.error('卸载失败') } }
async function loadSftpMounts() { try { sftpMounts.value = (await rescueApi.getSftpMounts()).mounts||[] } catch {} }

// ── File Browser ──
const fileBrowserVisible = ref(false); const browsePath = ref('/'); const dirItems = ref<any[]>([]); const browseCallback = ref<((p:string)=>void)|null>(null)
async function navigateTo(p: string) { try { const r = await rescueApi.listDirectory(p); dirItems.value = r.items||[]; browsePath.value = r.path||p } catch {} }
function openFileBrowser(currentPath: string) { browsePath.value = currentPath||'/'; navigateTo(browsePath.value); browseCallback.value = (p: string) => { isoPath.value = p }; fileBrowserVisible.value = true }
function onBrowseClick(row: any) { if(row.is_dir) navigateTo(row.path); else browsePath.value = row.path }
function selectBrowsePath() { if(browseCallback.value) browseCallback.value(browsePath.value); fileBrowserVisible.value = false }

// ── Grub + initramfs ──
const grubDisk = ref(''); const grubRoot = ref('/mnt'); const initramfsAll = ref(true)
const { state: taskRebuild, start: startRebuild } = useSseTask()
async function doGrubRepair() { try { const r = await rescueApi.grubRepair(grubDisk.value, grubRoot.value||''); toast.show(r.message, r.success?'success':'error') } catch { toast.error('操作失败') } }
async function doInitramfsRebuild() { try { const r = await rescueApi.rebuildInitramfs(initramfsAll.value); startRebuild(r.task_id) } catch { toast.error('操作失败') } }

// ── 系统快照备份 ──
const backupName = ref('')
const backupIncludeHome = ref(false)
const backupCreating = ref(false)
const backupResult = ref<any>(null)
const backups = ref<any[]>([])
const backupComparing = ref('')
const compareResult = ref<any>(null)

async function loadBackups() {
  try { backups.value = (await rescueApi.listBackups()).snapshots || [] } catch {}
}

async function doCreateBackup() {
  backupCreating.value = true
  backupResult.value = null
  try {
    const r = await rescueApi.createBackup(backupName.value, backupIncludeHome.value)
    backupResult.value = r
    if (r.success) { toast.success(`快照已创建: ${r.name}`); await loadBackups() }
    else toast.error(r.errors?.[0] || '创建失败')
  } catch { toast.error('备份创建失败') }
  finally { backupCreating.value = false }
}

async function doDeleteBackup(name: string) {
  if (!(await showConfirm('删除快照', `确定删除快照 ${name}？此操作不可逆。`, true))) return
  try {
    const r = await rescueApi.deleteBackup(name)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadBackups()
  } catch { toast.error('删除失败') }
}

async function doCompareBackup(name: string) {
  backupComparing.value = name
  try {
    compareResult.value = await rescueApi.compareBackup(name)
  } catch { toast.error('比较失败') }
  finally { backupComparing.value = '' }
}

// ── ISO 管理 ──
const isoPath = ref('/data/linux.iso')
const isoMountPoint = ref('/mnt/iso')
const isoConfigureRepo = ref(true)
const isoMounting = ref(false)
const mountedIsos = ref<IsoItem[]>([])
const repoStatus = ref<RepoStatus>({ configured: false, config_file: '', pkg_manager: '' })

// ── Chroot ──
const wsAvailable = ref(true)  // will be set false if WS connect fails
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

async function doMountIso() {
  if (!isoPath.value) { toast.warning('请输入 ISO 路径'); return }
  isoMounting.value = true
  try {
    const r = await rescueApi.mountIso(isoPath.value, isoMountPoint.value, isoConfigureRepo.value)
    if (r.success) {
      toast.success(r.message || '挂载成功')
      await loadMountedIsos()
      if (r.repo_configured) toast.success('本地源已配置: ' + r.distro_family)
    } else toast.error(r.message || '挂载失败')
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
  try { mountedIsos.value = (await rescueApi.getMountedIsos()).isos || [] } catch { toast.error('加载失败') }
}

async function loadRepoStatus() {
  try { repoStatus.value = await rescueApi.getRepoStatus() } catch { toast.error('加载失败') }
}

async function doRemoveRepo() {
  if (!(await showConfirm('移除本地源', '确定移除本地源配置？'))) return
  try {
    const r = await rescueApi.removeLocalRepo()
    toast.show(r.message, r.success ? 'success' : 'error')
    await loadRepoStatus()
  } catch { toast.error('操作失败') }
}

async function browseIso(mp: string) {
  browseVisible.value = true; browseLoading.value = true
  try {
    const r = await rescueApi.listIsoContent(mp)
    browseItems.value = r.items || []
  } catch { toast.error('加载失败') }
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
  try { chrootStatus.value = await rescueApi.getChrootStatus(chrootRoot.value) } catch { toast.error('加载失败') }
}

function onTermConnected() { /* */ }
function onTermDisconnected() { /* */ }

onMounted(() => { loadMountedIsos(); loadRepoStatus(); loadChrootStatus(); checkSshfs(); loadSftpMounts(); loadBackups(); fetchFeatures() })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
