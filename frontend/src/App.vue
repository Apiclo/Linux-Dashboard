<template>
  <div>
    <div v-if="route.name === 'login'">
      <RouterView />
    </div>
    <div v-else-if="initialized" class="app-layout" :class="{ 'sidebar-visible': sidebarOpen }">
      <button class="hamburger" @click="sidebarOpen = !sidebarOpen" :aria-label="sidebarOpen ? '关闭菜单' : '打开菜单'">
        <span></span><span></span><span></span>
      </button>
      <div class="sidebar-overlay" v-show="sidebarOpen" @click="sidebarOpen = false" />
      <AppSidebar :class="{ 'mobile-open': sidebarOpen }" @nav="sidebarOpen = false" />
      <main class="main-content" @click="sidebarOpen = false">
        <div class="breadcrumb-bar" v-if="route.name && route.name !== 'login'">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
        <button class="back-to-top" v-show="showBackTop" @click="scrollToTop" aria-label="回到顶部" title="回到顶部">↑</button>
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useAuth } from '@/composables/useAuth'
import { registerRouterAuth, setInitPromise } from '@/router'

const route = useRoute()
const router = useRouter()
const { authenticated, initialized, checkAuth } = useAuth()
const sidebarOpen = ref(false)

// Share the init promise with the router guard so it waits for our check
// instead of racing with a second API call.
const _initP = checkAuth()
setInitPromise(_initP)
registerRouterAuth(checkAuth, () => authenticated.value, () => initialized.value)

function onKeyDown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
  // Ctrl+K: 聚焦到第一个可搜索的 input（适配 Element Plus el-input 包装器）
  if (e.ctrlKey && e.key === 'k') { e.preventDefault(); const inp = document.querySelector('.el-input__inner:not([readonly])') || document.querySelector('input[type="text"]:not([readonly])') || document.querySelector('input:not([type]):not([readonly])'); if (inp instanceof HTMLInputElement) inp.focus() }
  // F5: 重新加载当前页面
  if (e.key === 'F5') { e.preventDefault(); router.go(0) }
  // Alt+1~9: 导航
  const navKeys: Record<string,string> = { '1':'/system','2':'/network','3':'/services','4':'/disk','5':'/gpu','6':'/packages','7':'/config','8':'/rescue' }
  if (e.altKey && navKeys[e.key]) { e.preventDefault(); router.push(navKeys[e.key]) }
  // ?: 键盘快捷键帮助
  if (e.key === '?' && !e.ctrlKey && !e.altKey && !e.metaKey) { e.preventDefault(); /* TODO: show shortcuts modal */ }
}

const showBackTop = ref(false)
function onScroll() { showBackTop.value = window.scrollY > 300 }
function scrollToTop() { window.scrollTo({ top: 0, behavior: 'smooth' }) }

onMounted(() => { window.addEventListener('keydown', onKeyDown); window.addEventListener('scroll', onScroll, { passive: true }) })
onBeforeUnmount(() => { window.removeEventListener('keydown', onKeyDown); window.removeEventListener('scroll', onScroll) })
onBeforeUnmount(() => { window.removeEventListener('keydown', onKeyDown) })
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

.breadcrumb-bar {
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Hamburger — visible only on mobile */
.hamburger {
  display: none;
  position: fixed;
  top: 12px; left: 12px;
  z-index: 1001;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
}
.hamburger span {
  display: block;
  width: 20px; height: 2px;
  background: var(--text-1);
  margin: 4px 0;
  border-radius: 2px;
}
.sidebar-overlay {
  position: fixed; inset: 0;
  z-index: 998;
  background: rgba(0,0,0,0.4);
}

/* Responsive sidebar */
@media (max-width: 768px) {
  .hamburger { display: block; }
  .main-content {
    margin-left: 0 !important;
    width: 100% !important;
    padding: 20px 16px !important;
  }
}
</style>
