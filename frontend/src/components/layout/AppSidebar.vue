<template>
  <div class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-icon">
        <el-icon :size="20" color="#fff"><Setting /></el-icon>
      </div>
      <div class="brand-text">
        <span class="brand-name">PenguinFu</span>
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
          <el-icon :size="15"><component :is="p.icon" /></el-icon>
          <div class="nav-item-info">
            <span class="nav-item-label">{{ p.label }}</span>
            <span class="nav-item-desc">{{ p.desc }}</span>
          </div>
        </router-link>
      </div>
    </nav>

    <div class="sidebar-footer">
      <div class="footer-info">{{ distro.id || 'Linux' }}</div>
      <div class="footer-actions">
        <button class="footer-btn" @click="toggleTheme" :title="theme === 'dark' ? '切换亮色' : '切换暗色'">
          <el-icon :size="16"><component :is="theme === 'dark' ? 'Sunny' : 'Moon'" /></el-icon>
        </button>
        <button class="footer-btn" @click="handleLogout" title="登出">
          <el-icon :size="16"><SwitchButton /></el-icon>
          <span class="footer-btn-text">{{ username }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { useDistro } from '@/composables/useDistro'

const router = useRouter()
const { username, logout } = useAuth()
const { distro, loadDistro } = useDistro()

const theme = ref(localStorage.getItem('theme') || 'dark')

const navGroups = [
  {
    label: '系统',
    items: [
      { to: '/system', label: '系统参数', icon: 'Monitor', desc: '主机名 · SSH · Swap · 内核' },
      { to: '/network', label: '网络设置', icon: 'Connection', desc: '接口 · 防火墙 · DNS' },
      { to: '/services', label: '服务管理', icon: 'Lightning', desc: 'systemd 服务控制' },
    ],
  },
  {
    label: '硬件 & 存储',
    items: [
      { to: '/disk', label: '磁盘管理', icon: 'Coin', desc: '挂载 · fstab · RAID' },
      { to: '/gpu', label: 'GPU 驱动', icon: 'VideoCamera', desc: 'NVIDIA · AMD · Intel' },
      { to: '/rescue', label: '系统救援', icon: 'SwitchFilled', desc: 'ISO源 · Chroot' },
    ],
  },
  {
    label: '软件',
    items: [
      { to: '/packages', label: '软件包', icon: 'Goods', desc: '搜索 · 安装 · 常用软件' },
      { to: '/config', label: '配置编辑', icon: 'EditPen', desc: '预设配置 · 参数修改' },
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
})
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: var(--bg-0);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
}

/* ── Brand ── */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px;
  border-bottom: 1px solid var(--border);
}
.brand-icon {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--accent), #a855f7);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-0);
  letter-spacing: -0.3px;
}
.brand-version {
  font-size: 11px;
  color: var(--text-2);
}

/* ── Navigation ── */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
}
.nav-group {
  margin-bottom: 4px;
}
.nav-group-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  padding: 16px 14px 6px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-1);
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s ease;
  text-decoration: none;
  margin: 1px 0;
  position: relative;
}
.nav-item:hover {
  background: var(--bg-3);
  color: var(--text-0);
}
.nav-item.active {
  background: rgba(88, 166, 255, 0.1);
  color: var(--accent);
  font-weight: 600;
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--accent);
}
.nav-item-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
}
.nav-item-label {
  font-size: 13px;
}
.nav-item-desc {
  font-size: 11px;
  color: var(--text-2);
  font-weight: 400;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Footer ── */
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.footer-info {
  font-size: 11px;
  color: var(--text-2);
  text-align: center;
}
.footer-actions {
  display: flex;
  gap: 6px;
}
.footer-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-1);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease;
}
.footer-btn:hover {
  background: var(--bg-3);
  color: var(--text-0);
  border-color: var(--text-2);
}
.footer-btn-text {
  max-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
