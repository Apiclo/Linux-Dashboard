<template>
  <el-card shadow="never">
    <template #header>
      <div class="flex justify-between items-center">
        <span class="flex items-center gap-2 font-semibold"><el-icon><Monitor /></el-icon>输出</span>
        <div class="flex gap-3 items-center">
          <el-tag v-if="running" type="info"><el-icon class="is-loading" :size="14"><Loading /></el-icon> 运行中</el-tag>
          <el-tag v-else-if="done" :type="exitCode === 0 ? 'success' : 'danger'">完成 ({{ exitCode }})</el-tag>
          <slot name="toolbar-extra" />
          <el-button v-if="running" size="small" type="danger" plain @click="$emit('cancel')"><el-icon class="mr-1"><Close /></el-icon>取消</el-button>
          <el-button v-if="showClear" size="small" plain @click="$emit('clear')"><el-icon class="mr-1"><Delete /></el-icon>清空</el-button>
          <el-button v-if="showCopy" size="small" plain @click="doCopy"><el-icon class="mr-1"><CopyDocument /></el-icon>复制</el-button>
        </div>
      </div>
    </template>
    <div class="terminal" ref="termEl" v-html="outputHtml || placeholder"></div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Monitor, Loading, Close, Delete, CopyDocument } from '@element-plus/icons-vue'
import { useToast } from '@/composables/useToast'

const props = withDefaults(defineProps<{
  outputHtml: string
  running?: boolean
  done?: boolean
  exitCode?: number
  placeholder?: string
  showClear?: boolean
  showCopy?: boolean
}>(), {
  running: false,
  done: false,
  exitCode: 0,
  placeholder: '',
  showClear: true,
  showCopy: true,
})

defineEmits<{
  clear: []
  cancel: []
}>()

const toast = useToast()
const termEl = ref<HTMLElement>()

watch(() => props.outputHtml, () => {
  nextTick(() => {
    if (termEl.value) termEl.value.scrollTop = termEl.value.scrollHeight
  })
})

async function doCopy() {
  await navigator.clipboard.writeText(termEl.value?.textContent || '')
  toast.success('已复制')
}
</script>

<style scoped>
.terminal { position: relative; }
</style>
