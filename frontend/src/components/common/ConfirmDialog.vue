<template>
  <el-dialog v-model="show" :title="title" width="450px" :close-on-click-modal="false">
    <div class="flex items-center gap-2 mb-3">
      <el-icon :size="20" :color="danger ? 'var(--red)' : 'var(--yellow)'">
        <WarningFilled />
      </el-icon>
      <span class="font-semibold">{{ title }}</span>
    </div>
    <p style="white-space: pre-line; line-height: 1.6; color: var(--text-1)">{{ message }}</p>
    <template #footer>
      <el-button @click="onCancel">取消</el-button>
      <el-button :type="danger ? 'danger' : 'primary'" @click="onConfirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { WarningFilled } from '@element-plus/icons-vue'
import { useConfirm } from '@/composables/useConfirm'
const { show, title, message, danger, onConfirm, onCancel } = useConfirm()
</script>
