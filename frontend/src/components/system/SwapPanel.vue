<template>
  <div class="p-5">
    <div class="flex flex-wrap gap-6 mb-3">
      <div><strong>总量:</strong> {{ info.total }}</div>
      <div><strong>已用:</strong> {{ info.used }}</div>
      <div><strong>可用:</strong> {{ info.free }}</div>
    </div>
    <el-table :data="info.files" size="small" stripe border class="mb-3" v-if="info.files.length">
      <el-table-column prop="path" label="路径" min-width="200" />
      <el-table-column prop="type" label="类型" width="100" />
      <el-table-column prop="size_kb" label="大小 (KB)" width="120" />
      <el-table-column prop="used_kb" label="已用 (KB)" width="120" />
    </el-table>
    <div class="flex gap-3 items-center flex-wrap">
      <el-input v-model="swapSize" placeholder="如 2G 或 512M" style="width: 160px" size="small" />
      <el-button size="small" type="primary" @click="createSwap" :loading="creating">创建 Swap</el-button>
      <el-button size="small" type="danger" @click="disableSwap" :loading="creating" :disabled="!info.files.length">关闭 Swap</el-button>
      <el-button size="small" @click="load">刷新</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { systemApi, type SwapInfo } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

const info = ref<SwapInfo>({ total: '0', used: '0', free: '0', files: [] })
const swapSize = ref('')
const creating = ref(false)

async function load() {
  try { info.value = await systemApi.getSwapInfo() } catch { /* ignore */ }
}

async function createSwap() {
  if (!swapSize.value.trim()) { toast.warning('请输入 Swap 大小'); return }
  creating.value = true
  try {
    const r = await systemApi.createSwap(swapSize.value.trim())
    toast.show(r.message || (r.success ? '已创建' : '失败'), r.success ? 'success' : 'error')
    if (r.success) { swapSize.value = ''; await load() }
  } finally { creating.value = false }
}

async function disableSwap() {
  const ok = await showConfirm('关闭 Swap', '确定要关闭所有 Swap 吗？这可能影响系统性能。')
  if (!ok) return
  creating.value = true
  try {
    const r = await systemApi.disableSwap()
    toast.show(r.message || (r.success ? '已关闭' : '失败'), r.success ? 'success' : 'error')
    if (r.success) await load()
  } finally { creating.value = false }
}

defineExpose({ load })
</script>
