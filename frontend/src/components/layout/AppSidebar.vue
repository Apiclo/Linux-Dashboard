<template>
  <div class="sidebar" :class="{ 'sidebar-open': mobileOpen }">
    <div class="sidebar-brand">
      <div class="brand-icon">
        <el-icon :size="22" color="#fff"><Setting /></el-icon>
      </div>
      <div class="brand-text">
        <span class="brand-name">TuxTackleBox</span>
        <span class="brand-version">v0.1.1-dev</span>
      </div>
    </div>

    <nav class="sidebar-nav">
      <div v-for="group in navGroups" :key="group.label" class="nav-group">
        <div class="nav-group-label">{{ group.label }}</div>
        <router-link
          v-for="p in group.items"
          :key="p.to"
          :to="p.to"
          class="nav-item"
          active-class="active"
        >
          <el-icon :size="18"><component :is="p.icon" /></el-icon>
          <span>{{ p.label }}</span>
        </router-link>
      </div>
    </nav>

    <div class="sidebar-footer">
      <div class="footer-info">{{ distro.id || 'Linux' }}</div>
      <div class="footer-actions">
        <button class="footer-btn" @click="toggleTheme" :title="theme === 'dark' ? '切换亮色' : '切换暗色'">
          <el-icon :size="17"><component :is="theme === 'dark' ? 'Sunny' : 'Moon'" /></el-icon>
        </button>
        <button class="footer-btn" @click="handleLogout" title="登出">
          <el-icon :size="17"><SwitchButton /></el-icon>
          <span class="footer-btn-text">{{ username }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { useDistro } from '@/composables/useDistro'

const router = useRouter()
const { username, logout } = useAuth()
const { distro, loadDistro } = useDistro()

const mobileOpen = ref(false)
function toggleMobile() { mobileOpen.value = !mobileOpen.value }
function closeMobile() { mobileOpen.value = false }

const theme = ref(localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))
let _mqListener: MediaQueryList | null = null

function onThemeChange(e: MediaQueryListEvent) {
  if (!localStorage.getItem('theme')) {
    theme.value = e.matches ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', theme.value)
    document.documentElement.classList.toggle('dark', theme.value === 'dark')
  }
}

const navGroups = [
  {
    label: '系统',
    items: [
      { to: '/', label: '概览', icon: 'DataBoard' },
      { to: '/system', label: '系统', icon: 'Monitor' },
      { to: '/kernel', label: '内核', icon: 'Cpu' },
      { to: '/processes', label: '进程', icon: 'Monitor' },
      { to: '/users', label: '用户', icon: 'User' },
      { to: '/logs', label: '日志', icon: 'Tickets' },
    ],
  },
  {
    label: '网络与服务',
    items: [
      { to: '/network', label: '网络', icon: 'Connection' },
      { to: '/services', label: '服务', icon: 'Lightning' },
    ],
  },
  {
    label: '存储',
    items: [
      { to: '/disk', label: '磁盘', icon: 'Coin' },
      { to: '/gpu', label: 'GPU', icon: 'VideoCamera' },
      { to: '/rescue', label: '救援', icon: 'SwitchFilled' },
    ],
  },
  {
    label: '软件',
    items: [
      { to: '/packages', label: '软件包', icon: 'Goods' },
      { to: '/config', label: '配置', icon: 'EditPen' },
    ],
  },
]

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', theme.value)
  document.documentElement.classList.toggle('dark', theme.value === 'dark')
  localStorage.setItem('theme', theme.value)
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

onMounted(() => {
  document.documentElement.setAttribute('data-theme', theme.value)
  document.documentElement.classList.toggle('dark', theme.value === 'dark')
  loadDistro()
  // Follow system theme changes
  _mqListener = window.matchMedia('(prefers-color-scheme: dark)')
  _mqListener.addEventListener('change', onThemeChange)
})

onBeforeUnmount(() => {
  _mqListener?.removeEventListener('change', onThemeChange)
  _mqListener = null
})
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: var(--sidebar-bg);
  display: flex; flex-direction: column;
  height: 100vh; position: fixed;
  left: 0; top: 0; z-index: 100;
}

/* Brand */
.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.brand-icon {
  width: 32px; height: 32px; border-radius: 5px;
  background: var(--accent);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.brand-text { display: flex; flex-direction: column; gap: 1px; }
.brand-name { font-size: 15px; font-weight: 700; color: #fff; letter-spacing: -0.2px; }
.brand-version { font-size: 10px; color: #777; }

/* Navigation */
.sidebar-nav { flex: 1; overflow-y: auto; padding: 8px 8px; }
.nav-group { margin-bottom: 4px; }
.nav-group-label {
  font-size: 10px; font-weight: 700; color: #666;
  text-transform: uppercase; letter-spacing: 1.2px;
  padding: 16px 14px 6px;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-radius: 5px;
  cursor: pointer; color: var(--sidebar-text);
  font-size: 13px; font-weight: 500;
  transition: all 0.15s; text-decoration: none;
  margin: 2px 0;
}
.nav-item:hover { background: var(--sidebar-hover); color: #ccc; }
.nav-item.active { background: rgba(255,255,255,0.12); color: var(--sidebar-active); font-weight: 600; }

/* Footer */
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
  display: flex; flex-direction: column; gap: 8px;
}
.footer-info { font-size: 10px; color: #555; text-align: center; }
.footer-actions { display: flex; gap: 6px; }
.footer-btn {
  flex: 1; display: flex; align-items: center; justify-content: center;
  gap: 6px; padding: 7px 10px;
  border: 1px solid rgba(255,255,255,0.1); border-radius: 4px;
  background: transparent; color: #999;
  cursor: pointer; font-size: 11px; transition: all 0.15s;
}
.footer-btn:hover { background: rgba(255,255,255,0.08); color: #ccc; }
.footer-btn-text { max-width: 64px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
