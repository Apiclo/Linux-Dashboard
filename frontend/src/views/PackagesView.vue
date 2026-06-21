<template>
  <div>
    <div class="page-title"><el-icon><Goods /></el-icon>软件包</div>

    <!-- 发行版信息 -->
    <el-alert type="info" :closable="false" class="mb-5">
      <template #title>
        {{ distro.pretty_name || distro.id }} | {{ distro.pkg_manager }}
        <el-tag v-if="distro.is_kylin" type="warning" class="ml-2">Kylin</el-tag>
      </template>
    </el-alert>

    <!-- 搜索安装 -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <span class="flex items-center gap-2 font-semibold"><el-icon><Search /></el-icon>搜索安装</span>
      </template>
      <div class="flex gap-3 mb-3 items-center">
        <el-input v-model="query" placeholder="搜索包名..." class="flex-1" size="small" @keyup.enter="doSearch" />
        <el-button size="small" plain :icon="Search" @click="doSearch">搜索</el-button>
      </div>
      <el-table v-if="searchRows.length" :data="searchRows" size="small" stripe border class="mb-3" max-height="400">
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
      <div v-else-if="searchResult" class="text-sm mb-3" style="color: var(--text-2)">{{ searchResult }}</div>
      <el-divider />
      <div class="flex gap-3 items-center">
        <el-input v-model="pkgName" placeholder="包名" class="flex-1" size="small" @keyup.enter="doInstall" />
        <el-button size="small" @click="doInstall" :disabled="!pkgName || task.running">安装</el-button>
        <el-button size="small" type="danger" @click="doRemove" :disabled="!pkgName || task.running">卸载</el-button>
        <el-button size="small" type="warning" @click="doSystemUpdate" :disabled="task.running">
          <el-icon><Refresh /></el-icon>系统更新
        </el-button>
      </div>
    </el-card>

    <!-- 常用软件 -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <span class="flex items-center gap-2 font-semibold"><el-icon><Grid /></el-icon>常用软件</span>
      </template>
      <el-tabs v-model="swCat">
        <el-tab-pane v-for="(items, cat) in software" :key="cat" :label="String(cat)" :name="String(cat)">
          <div class="grid grid-cols-12 gap-4">
            <div class="col-span-12 md:col-span-4" v-for="(info, id) in items" :key="id">
              <div
                class="sw-card p-3 flex gap-3 items-center cursor-pointer rounded-lg transition-all"
                @click="installSw(info[distro.pkg_manager] || String(id), String(id))"
              >
                <div class="text-3xl flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg" style="background: var(--bg-3)">
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

    <!-- 输出 -->
    <TerminalOutput
      :outputHtml="outputHtml"
      :running="task.running"
      @cancel="taskStop"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Refresh, Grid } from '@element-plus/icons-vue'
import { packagesApi } from '@/api/packages'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useSseTask } from '@/composables/useSseTask'
import type { DistroInfo } from '@/types/api'
import TerminalOutput from '@/components/terminal/TerminalOutput.vue'

const toast = useToast()
const { state: task, start, stop, outputHtml } = useSseTask()
const distro = ref<DistroInfo>({} as DistroInfo)
const software = ref<Record<string, Record<string, any>>>({})
const swCat = ref('')
const query = ref('')
const searchResult = ref('')
const pkgName = ref('')

interface SearchRow {
  name: string
  version: string
  description: string
}

const searchRows = computed<SearchRow[]>(() => {
  if (!searchResult.value || searchResult.value === '未找到' || searchResult.value === '搜索失败') return []
  return searchResult.value.split('\n').filter(l => l.trim()).map(line => {
    const parts = line.trim().split(/\s{2,}/)
    if (parts.length >= 3) return { name: parts[0], version: parts[1], description: parts.slice(2).join(' ') }
    if (parts.length === 2) return { name: parts[0], version: '', description: parts[1] }
    return { name: parts[0] || line, version: '', description: '' }
  })
})

async function load() {
  try {
    const [d, sw] = await Promise.all([systemApi.getDistro(), packagesApi.getSoftware()])
    distro.value = d; software.value = sw; swCat.value = Object.keys(sw)[0] || ''
  } catch {}
}

async function doSearch() {
  if (!query.value) return
  try { const r = await packagesApi.search(query.value); searchResult.value = r.result || '未找到' } catch { searchResult.value = '搜索失败' }
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

onMounted(load)
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
