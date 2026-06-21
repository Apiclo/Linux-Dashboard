<template>
  <div>
    <div class="page-title"><el-icon><Goods /></el-icon>软件包</div>

    <FeatureStatus :features="features" />

    <!-- 发行版信息 -->
    <div v-if="distroLoading" class="panel-loading"><el-icon class="is-loading"><Loading /></el-icon> 检测发行版信息...</div>
    <el-alert v-else type="info" :closable="false" class="mb-6" style="margin-bottom: 20px">
      <template #title>
        {{ distro.pretty_name || distro.id }} | {{ distro.pkg_manager }}
        <el-tag v-if="distro.is_kylin" type="warning" class="ml-2">Kylin</el-tag>
      </template>
    </el-alert>

    <!-- 搜索安装 -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Search /></el-icon>搜索安装</span>
      </template>
      <div class="flex gap-4 mb-4 items-center">
        <el-input v-model="queryRaw" placeholder="搜索包名（自动搜索）..." class="flex-1" size="small" />
        <el-button size="small" plain :icon="Search" @click="doSearch">搜索</el-button>
      </div>
      <el-table v-if="searchResults.length" :data="searchResults" size="small" stripe border class="mb-3" max-height="400">
        <el-table-column prop="name" label="包名" min-width="180">
          <template #default="{ row }"><span class="font-mono text-sm">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="140" />
        <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="quickInstall(row.name)" :disabled="task.running">安装</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="hasSearched" description="未找到相关软件包" :image-size="60" />
      <el-divider />
      <div class="flex gap-4 items-center">
        <el-input v-model="pkgName" placeholder="包名" class="flex-1" size="small" @keyup.enter="doInstall" />
        <el-button size="small" @click="doInstall" :disabled="!pkgName || task.running">安装</el-button>
        <el-button size="small" type="danger" @click="doRemove" :disabled="!pkgName || task.running">卸载</el-button>
        <el-button size="small" type="warning" @click="doSystemUpdate" :disabled="task.running">
          <el-icon><Refresh /></el-icon>系统更新
        </el-button>
      </div>
    </el-card>

    <!-- ═══════════ 已安装 / 源 / 历史 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header><span class="flex items-center gap-3 font-semibold"><el-icon><List /></el-icon>管理</span></template>
      <el-tabs v-model="mgmtTab">
        <el-tab-pane name="installed">
          <template #label><span class="text-sm">已安装</span></template>
          <div class="flex gap-3 mb-4 items-center">
            <el-input v-model="installedFilterRaw" placeholder="搜索已安装包..." size="small" class="w-64" @keyup.enter="loadInstalled" />
            <el-button size="small" plain @click="loadInstalled">搜索</el-button>
          </div>
          <el-table v-if="installedPkgs.length" :data="paginatedInstalled" size="small" stripe border max-height="350" @selection-change="onInstalledSelect" @sort-change="onInstalledSort">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="name" label="包名" min-width="200" sortable="custom"><template #default="{row}"><span class="font-mono text-sm">{{row.name}}</span></template></el-table-column>
            <el-table-column prop="version" label="版本" width="160" sortable="custom" />
            <el-table-column label="操作" width="80"><template #default="{row}"><el-button size="small" type="danger" plain @click="doRemoveInstalled(row.name)">卸载</el-button></template></el-table-column>
          </el-table>
          <el-pagination
            class="mt-4"
            layout="prev, pager, next, sizes"
            :page-sizes="[20, 50, 100]"
            :page-size="installedPageSize"
            :total="paginatedInstalled.length"
            :current-page="installedPage"
            size="small"
            @size-change="onInstalledSizeChange"
            @current-change="onInstalledPageChange"
          />
          <div v-if="installedSelected.length" class="mt-3"><el-button size="small" type="danger" @click="doBatchRemove">批量卸载 ({{installedSelected.length}})</el-button></div>
        </el-tab-pane>
        <el-tab-pane name="cleanup">
          <template #label><span class="text-sm">清理</span></template>
          <div class="grid grid-cols-12 gap-4">
            <div class="col-span-12 md:col-span-6">
              <div class="font-semibold text-sm mb-2">孤立包 / 残留配置</div>
              <el-button size="small" @click="loadOrphans" :loading="orphansLoading">检测</el-button>
              <div v-if="orphans.orphans?.length" class="mt-3">
                <div v-for="(o,i) in orphans.orphans.slice(0,30)" :key="i" class="flex items-center justify-between py-1 text-xs">
                  <span class="font-mono">{{ o.name }}</span>
                  <span style="color:var(--text-2)">{{ o.reason }}</span>
                </div>
              </div>
              <div v-if="orphans.suggestions?.length" class="mt-3">
                <div class="text-xs font-semibold mb-1" style="color:var(--yellow)">建议检查:</div>
                <div v-for="(s,i) in orphans.suggestions.slice(0,15)" :key="i" class="text-xs font-mono py-0.5">{{ s.name }} <span style="color:var(--text-2)">— {{ s.reason }}</span></div>
              </div>
            </div>
            <div class="col-span-12 md:col-span-6">
              <div class="font-semibold text-sm mb-2">缓存清理</div>
              <div class="text-xs mb-2" style="color:var(--text-2)">清理包管理器缓存，释放磁盘空间</div>
              <el-button size="small" type="warning" @click="doCleanCache" :loading="cacheCleaning">清理缓存</el-button>
              <div v-if="cacheResult" class="mt-2 text-xs">
                <div v-if="cacheResult.before">清理前: {{ cacheResult.before }}</div>
                <div v-if="cacheResult.after">清理后: {{ cacheResult.after }}</div>
                <div v-if="cacheResult.freed" class="mt-1" style="color:var(--green)">{{ cacheResult.freed }}</div>
              </div>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane name="repos">
          <template #label><span class="text-sm">软件源</span></template>
          <div v-if="repoData.repos?.length" class="mb-3">
            <el-table :data="repoData.repos" size="small" stripe border>
              <el-table-column label="详情" min-width="300"><template #default="{row}"><span class="font-mono text-sm">{{row.line||row.name||row.baseurl}}</span></template></el-table-column>
              <el-table-column prop="file" label="文件" width="200"><template #default="{row}"><span class="text-xs" style="color:var(--text-2)">{{row.file}}</span></template></el-table-column>
            </el-table>
          </div>
          <div class="flex gap-3 items-center">
            <el-input v-model="repoUrl" placeholder="源 URL 或完整行" size="small" class="w-64" @keyup.enter="doAddRepo" />
            <el-button size="small" @click="doAddRepo">添加</el-button>
            <el-button size="small" plain @click="loadRepos">刷新</el-button>
          </div>
          <el-divider />
          <el-button size="small" plain @click="openRepoRawDialog">编辑源文件</el-button>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 常用软件 -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Grid /></el-icon>常用软件</span>
      </template>
      <el-tabs v-model="swCat">
        <el-tab-pane v-for="(items, cat) in software" :key="cat" :label="String(cat)" :name="String(cat)">
          <div class="grid grid-cols-12 gap-4">
            <div class="col-span-12 md:col-span-4" v-for="(info, id) in items" :key="id">
              <div
                class="sw-card p-3 flex gap-4 items-center cursor-pointer rounded-lg transition-all"
                @click="installSw(info[distro.pkg_manager] || String(id), String(id))"
              >
                <div class="text-2xl flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg overflow-hidden leading-none" style="background: var(--bg-3)">
                  {{ info.icon || info.emoji || '📦' }}
                </div>
                <div class="flex-1 min-w-0">
                  <div class="font-semibold text-sm truncate">{{ id }}</div>
                  <div class="text-xs truncate" style="color: var(--text-1)">{{ info.desc }}</div>
                </div>
                <el-button size="small" @click.stop="installSw(info[distro.pkg_manager] || String(id), String(id))" :disabled="task.running">安装</el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 源文件编辑对话框 -->
    <el-dialog v-model="showRepoRawDialog" title="编辑源文件" width="700px">
      <div v-if="!Object.keys(repoRawFiles).length" class="text-center py-8" style="color: var(--text-2)">
        未找到源配置文件
      </div>
      <template v-else>
        <el-select v-model="repoRawFile" class="w-full mb-3" size="small" placeholder="选择文件">
          <el-option v-for="(content, path) in repoRawFiles" :key="path" :label="path" :value="path" />
        </el-select>
        <el-input v-model="repoRawContent" type="textarea" :rows="15" class="w-full mono-textarea" />
      </template>
      <template #footer>
        <el-button @click="showRepoRawDialog = false">取消</el-button>
        <el-button type="primary" @click="doSaveRepoRaw" :loading="repoRawSaving" :disabled="!Object.keys(repoRawFiles).length">保存</el-button>
      </template>
    </el-dialog>

    <!-- 输出 -->
    <TerminalOutput
      :outputHtml="outputHtml"
      :running="task.running"
      @cancel="taskStop"
    />
    <!-- Batch operation result summary -->
    <div v-if="task.done && batchResult" class="mt-3 p-4 rounded-lg" style="background: var(--bg-0); border: 1px solid var(--border-1)">
      <div class="flex items-center gap-2 mb-1">
        <el-icon :size="16"><InfoFilled /></el-icon>
        <span class="font-semibold text-sm">批量操作结果</span>
        <el-tag :type="batchResult.failed === 0 ? 'success' : 'warning'" size="small">{{ batchResult.summary }}</el-tag>
      </div>
      <div v-if="batchResult.failedPackages.length" class="mt-3">
        <div class="text-xs mb-1" style="color: var(--text-error)">失败列表:</div>
        <div class="flex flex-wrap gap-1">
          <el-tag v-for="pkg in batchResult.failedPackages" :key="pkg" size="small" type="danger">{{ pkg }}</el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { Search, Refresh, Grid, List, InfoFilled } from '@element-plus/icons-vue'
import { packagesApi } from '@/api/packages'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useSseTask } from '@/composables/useSseTask'
import { useDebounce } from '@/composables/useDebounce'
import type { DistroInfo, SearchPackageResult } from '@/types/api'
import TerminalOutput from '@/components/terminal/TerminalOutput.vue'

const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['package_manager','sudo','snap','flatpak'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }
const { state: task, start, stop, outputHtml, parsedResults: batchResult } = useSseTask()
const distro = ref<DistroInfo>({} as DistroInfo)
const distroLoading = ref(true)
const software = ref<Record<string, Record<string, any>>>({})
const swCat = ref('')
const queryRaw = ref('')
const query = useDebounce(queryRaw, 300)
// Auto-search when debounced query changes
watch(query, (val) => { if (val) doSearch() })
const searchResults = ref<SearchPackageResult[]>([])
const hasSearched = ref(false)
const pkgName = ref('')

async function load() {
  distroLoading.value = true
  try {
    const [d, sw] = await Promise.all([systemApi.getDistro(), packagesApi.getSoftware()])
    distro.value = d; software.value = sw; swCat.value = Object.keys(sw)[0] || ''
  } catch { toast.error('加载软件包信息失败') } finally {
    distroLoading.value = false
  }
}

async function doSearch() {
  if (!query.value) return
  hasSearched.value = true
  try {
    const r = await packagesApi.searchStructured(query.value)
    searchResults.value = r.results || []
  } catch {
    searchResults.value = []
    toast.error('搜索失败')
  }
}

async function doInstall() {
  if (!pkgName.value) return
  const r = await packagesApi.install(pkgName.value); start(r.task_id)
}

async function doRemove() {
  if (!pkgName.value) return
  const r = await packagesApi.remove(pkgName.value); start(r.task_id)
}

async function quickInstall(name: string) {
  pkgName.value = name
  await doInstall()
}

async function installSw(pkg: string, name: string) {
  if (!pkg) return
  const r = await packagesApi.install(pkg); start(r.task_id); toast.info(`正在安装 ${name}...`)
}

async function doSystemUpdate() {
  try {
    const r = await systemApi.update()
    start(r.task_id)
    toast.info('正在执行系统更新...')
  } catch { toast.error('系统更新请求失败') }
}

function taskStop() { stop(); toast.info('已取消') }

// ── 已安装包 ──
const mgmtTab = ref('installed')
const installedPkgs = ref<any[]>([]); const installedSelected = ref<string[]>([]); const installedFilterRaw = ref('')
const installedFilter = useDebounce(installedFilterRaw, 300)
const installedPage = ref(1)
const installedPageSize = ref(50)
const installedSortKey = ref('')
const installedSortOrder = ref<'ascending' | 'descending' | null>(null)
function onInstalledSelect(rows: any[]) { installedSelected.value = rows.map((r: any) => r.name) }
async function loadInstalled() { try { installedPkgs.value = (await packagesApi.getInstalled(installedFilterRaw.value)).packages||[]; installedPage.value = 1 } catch { toast.error('加载失败') } }
async function doRemoveInstalled(name: string) { pkgName.value = name; await doRemove() }
async function doBatchRemove() { if(!installedSelected.value.length) return; try { const r = await packagesApi.batchRemove(installedSelected.value); start(r.task_id); installedSelected.value = [] } catch { toast.error('操作失败') } }

const sortedInstalled = computed(() => {
  const arr = [...installedPkgs.value]
  if (installedSortKey.value && installedSortOrder.value) {
    arr.sort((a, b) => {
      const va = a[installedSortKey.value] ?? ''
      const vb = b[installedSortKey.value] ?? ''
      if (va < vb) return installedSortOrder.value === 'ascending' ? -1 : 1
      if (va > vb) return installedSortOrder.value === 'ascending' ? 1 : -1
      return 0
    })
  }
  return arr
})

const paginatedInstalled = computed(() => {
  const start = (installedPage.value - 1) * installedPageSize.value
  return sortedInstalled.value.slice(start, start + installedPageSize.value)
})

function onInstalledSort({ prop, order }: { prop: string; order: string }) {
  installedSortKey.value = prop
  installedSortOrder.value = order as 'ascending' | 'descending' | null
  installedPage.value = 1
}

function onInstalledSizeChange(s: number) { installedPageSize.value = s; installedPage.value = 1 }
function onInstalledPageChange(p: number) { installedPage.value = p }

// ── 软件源 ──
const repoData = ref<Record<string,any>>({ repos: [], files: [] }); const repoUrl = ref('')
async function loadRepos() { try { repoData.value = await packagesApi.getRepos() } catch {} }
async function doAddRepo() { if(!repoUrl.value) return; try { const r = await packagesApi.addRepo(repoUrl.value); toast.show(r.message, r.success?'success':'error'); if(r.success){ repoUrl.value=''; await loadRepos() } } catch { toast.error('添加失败') } }

// ── 源文件编辑 ──
const showRepoRawDialog = ref(false)
const repoRawFiles = ref<Record<string, string>>({})
const repoRawFile = ref('')
const repoRawContent = ref('')
const repoRawSaving = ref(false)

async function openRepoRawDialog() {
  try {
    const r = await packagesApi.getRepoRaw()
    repoRawFiles.value = r.files || {}
    repoRawFile.value = Object.keys(repoRawFiles.value)[0] || ''
    repoRawContent.value = repoRawFiles.value[repoRawFile.value] || ''
  } catch { toast.error('加载源文件失败') }
  showRepoRawDialog.value = true
}

watch(repoRawFile, (newPath) => {
  if (newPath) repoRawContent.value = repoRawFiles.value[newPath] || ''
})

async function doSaveRepoRaw() {
  if (!repoRawFile.value) return
  repoRawSaving.value = true
  try {
    const r = await packagesApi.saveRepoRaw(repoRawFile.value, repoRawContent.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) showRepoRawDialog.value = false
  } catch { toast.error('保存失败') }
  finally { repoRawSaving.value = false }
}

// ── 清理 ──
const orphans = ref<{ orphans: any[]; suggestions: any[] }>({ orphans: [], suggestions: [] })
const orphansLoading = ref(false)
const cacheCleaning = ref(false)
const cacheResult = ref<any>(null)
async function loadOrphans() { orphansLoading.value = true; try { orphans.value = await packagesApi.getOrphans() } catch { toast.error('检测失败') } finally { orphansLoading.value = false } }
async function doCleanCache() { cacheCleaning.value = true; try { cacheResult.value = await packagesApi.cleanCache(); toast.success('缓存已清理') } catch { toast.error('清理失败') } finally { cacheCleaning.value = false } }

onMounted(() => { load(); loadInstalled(); loadRepos(); fetchFeatures() })
</script>

<style scoped>
.sw-card {
  background: var(--bg-2, var(--bg-0));
  border: 1px solid transparent;
  transition: all 0.2s ease;
}
.sw-card:hover {
  border-color: var(--accent, #409eff);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
