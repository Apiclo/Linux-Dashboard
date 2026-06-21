<template>
  <div class="feature-status-bar" v-if="features.length">
    <el-tag
      v-for="f in features" :key="f.name"
      :type="f.available ? 'success' : 'danger'"
      size="small"
      effect="plain"
      class="feature-tag"
    >
      {{ f.available ? '✓' : '✗' }} {{ f.name }}
    </el-tag>
  </div>
</template>

<script setup lang="ts">
defineProps<{ features: Array<{ name: string; available: boolean }> }>()
</script>

<style scoped>
.feature-status-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.feature-tag { font-family: monospace; font-size: 12px; }
</style>
