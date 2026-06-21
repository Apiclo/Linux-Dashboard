<template>
  <div>
    <div v-if="route.name === 'login'">
      <RouterView />
    </div>
    <div v-else-if="initialized" class="app-layout">
      <AppSidebar />
      <main class="main-content">
        <RouterView />
      </main>
    </div>
    <div v-else class="loading-screen">
      <div class="loading-spinner">
        <el-icon class="is-loading" :size="36" color="var(--accent)"><Loading /></el-icon>
        <span class="loading-text">正在加载...</span>
      </div>
    </div>
    <ConfirmDialog />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useAuth } from '@/composables/useAuth'
import { registerRouterAuth } from '@/router'

const route = useRoute()
const { authenticated, initialized, checkAuth } = useAuth()

registerRouterAuth(checkAuth, () => authenticated.value, () => initialized.value)

onMounted(() => { checkAuth() })
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background-color: var(--bg-0);
}

.main-content {
  margin-left: var(--sidebar-w);
  min-height: 100vh;
  padding: 32px 40px;
  width: calc(100% - var(--sidebar-w));
  box-sizing: border-box;
}

.loading-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-0);
}
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.loading-text {
  color: var(--text-2);
  font-size: 14px;
}
</style>
