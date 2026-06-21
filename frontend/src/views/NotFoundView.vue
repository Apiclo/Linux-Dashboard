<template>
  <div class="not-found-container">
    <h1 class="not-found-code">404</h1>
    <p class="not-found-message">页面未找到</p>
    <el-button type="primary" @click="$router.push('/system')">返回首页</el-button>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.not-found-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 60vh;
  gap: 16px;
}
.not-found-code {
  font-size: 72px;
  font-weight: 700;
  color: var(--text-2);
  margin: 0;
}
.not-found-message {
  font-size: 18px;
  color: var(--text-1);
  margin: 0;
}
</style>
