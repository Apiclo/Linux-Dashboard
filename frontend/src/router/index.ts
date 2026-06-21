import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '概览' } },
    { path: '/system', name: 'system', component: () => import('@/views/SystemView.vue'), meta: { title: '系统参数' } },
    { path: '/kernel', name: 'kernel', component: () => import('@/views/KernelView.vue'), meta: { title: '内核调优' } },
    { path: '/processes', name: 'processes', component: () => import('@/views/ProcessesView.vue'), meta: { title: '进程管理' } },
    { path: '/users', name: 'users', component: () => import('@/views/UsersView.vue'), meta: { title: '用户管理' } },
    { path: '/logs', name: 'logs', component: () => import('@/views/LogsView.vue'), meta: { title: '日志与安全' } },
    { path: '/network', name: 'network', component: () => import('@/views/NetworkView.vue'), meta: { title: '网络设置' } },
    { path: '/services', name: 'services', component: () => import('@/views/ServicesView.vue'), meta: { title: '服务管理' } },
    { path: '/disk', name: 'disk', component: () => import('@/views/DiskView.vue'), meta: { title: '磁盘管理' } },
    { path: '/gpu', name: 'gpu', component: () => import('@/views/GpuView.vue'), meta: { title: 'GPU 驱动' } },
    { path: '/packages', name: 'packages', component: () => import('@/views/PackagesView.vue'), meta: { title: '软件包' } },
    { path: '/config', name: 'config', component: () => import('@/views/ConfigView.vue'), meta: { title: '配置编辑' } },
    { path: '/rescue', name: 'rescue', component: () => import('@/views/RescueView.vue'), meta: { title: '系统救援' } },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue'), meta: { title: '页面未找到' } },
  ],
})

// ── Auth state: initialized from App.vue, checked by router guard ──
let _authCheck: (() => Promise<boolean>) | null = null
let _isAuthenticated: (() => boolean) | null = null
let _isInitialized: (() => boolean) | null = null
let _initPromise: Promise<boolean> | null = null

export function setInitPromise(p: Promise<boolean>) { _initPromise = p }

export function registerRouterAuth(checkFn: () => Promise<boolean>, isAuthFn: () => boolean, isInitFn: () => boolean) {
  _authCheck = checkFn
  _isAuthenticated = isAuthFn
  _isInitialized = isInitFn
}

router.beforeEach(async (to) => {
  document.title = `TuxTackleBox - ${to.meta.title || ''}`

  // Public routes (login page) - always allow
  if (to.meta.public) return

  // If auth functions not registered yet (shouldn't happen), allow
  if (!_authCheck || !_isAuthenticated || !_isInitialized) return

  // If not initialized yet, wait for App.vue's check to avoid duplicate API call
  if (!_isInitialized()) {
    const ok = _initPromise ? await _initPromise : (_authCheck ? await _authCheck() : true)
    if (!ok) return { name: 'login' }
    return
  }

  // Already initialized: check local state (no network request)
  if (!_isAuthenticated()) {
    return { name: 'login' }
  }
})

export default router
