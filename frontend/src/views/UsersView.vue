<template>
  <div>
    <div class="page-title">
      <el-icon><User /></el-icon>用户管理
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新 (30s)" />
    </div>

    <FeatureStatus :features="features" />

    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><User /></el-icon>本地用户</span>
      </template>
      <UserManagementPanel :key="refreshKey" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { systemApi } from '@/api/system'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import UserManagementPanel from '@/components/system/UserManagementPanel.vue'
import { User } from '@element-plus/icons-vue'

const features = ref<Array<{ name: string; available: boolean }>>([])
async function fetchFeatures() {
  try {
    const f = await systemApi.getFeatures()
    features.value = Object.entries(f).map(([k, v]) => ({ name: k, available: !!v }))
  } catch { /* non-critical */ }
}

// Auto-refresh — UserManagementPanel handles its own data loading internally,
// so this just triggers a re-render of the component
const autoRefresh = ref(false)
const refreshKey = ref(0)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(() => { refreshKey.value++ }, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}

onMounted(() => { fetchFeatures() })
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>
