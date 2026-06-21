<template>
  <div class="p-5">
    <div class="flex items-center justify-between mb-3">
      <el-input v-model="filter" placeholder="搜索模块..." size="small" style="width: 240px" />
      <el-button size="small" plain @click="load">刷新</el-button>
    </div>
    <el-table :data="filteredList" size="small" stripe border height="350px">
      <el-table-column prop="name" label="名称" min-width="180">
        <template #default="{ row }"><span class="font-mono">{{ row.name }}</span></template>
      </el-table-column>
      <el-table-column prop="size" label="大小" width="100" />
      <el-table-column prop="used_by" label="引用计数" width="100" />
      <el-table-column prop="used_by_list" label="使用方" min-width="200">
        <template #default="{ row }"><span class="font-mono text-xs" style="color: var(--text-2)">{{ row.used_by_list || '-' }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button size="small" type="danger" plain @click="doManageModule(row.name, 'unload')" :disabled="row.used_by > 0">卸载</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!filteredList.length" description="无匹配模块" :image-size="60" />
    <div class="flex gap-3 items-center mt-3">
      <el-input v-model="moduleName" placeholder="模块名称" size="small" style="width: 200px" />
      <el-button size="small" type="primary" @click="doManageModule(moduleName, 'load')">加载模块</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

interface ModuleEntry {
  name: string
  size: string
  used_by: number
  used_by_list: string
}

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

const modules = ref<ModuleEntry[]>([])
const filter = ref('')
const moduleName = ref('')

const filteredList = computed(() => {
  const q = filter.value.toLowerCase()
  if (!q) return modules.value.slice(0, 200)
  return modules.value.filter(m => m.name.toLowerCase().includes(q)).slice(0, 200)
})

async function load() {
  try {
    const r = await systemApi.getModules()
    modules.value = r.modules || []
  } catch { /* ignore */ }
}

async function doManageModule(name: string, action: string) {
  if (!name.trim()) return toast.warning('请输入模块名称')
  const label = action === 'load' ? '加载' : '卸载'
  if (!(await showConfirm(label, `确定${label}模块 ${name}？`))) return
  const r = await systemApi.manageModule(name.trim(), action)
  toast.show(r.message, r.success ? 'success' : 'error')
  if (r.success) await load()
}

defineExpose({ load })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }
</style>
