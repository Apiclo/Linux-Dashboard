import { ref } from 'vue'
import { authApi } from '@/api/auth'
import { registerAuthClear } from '@/api/request'

const authenticated = ref(false)
const username = ref('')
const loading = ref(false)
const initialized = ref(false)

// Register the clear function so request.ts can clear auth state on 401
registerAuthClear(() => {
  authenticated.value = false
  username.value = ''
  initialized.value = false
})

export function useAuth() {
  /**
   * Check auth status with backend. Called once on app init.
   * After that, auth state is maintained locally.
   */
  async function checkAuth(): Promise<boolean> {
    try {
      const res = await authApi.status()
      authenticated.value = res.authenticated
      username.value = res.username || ''
      initialized.value = true
      return res.authenticated
    } catch {
      authenticated.value = false
      username.value = ''
      initialized.value = true
      return false
    }
  }

  async function login(user: string, pass: string): Promise<{ success: boolean; message: string }> {
    loading.value = true
    try {
      const res = await authApi.login(user, pass)
      if (res.success) {
        authenticated.value = true
        username.value = res.username
        initialized.value = true
      }
      return res
    } catch (e: any) {
      return { success: false, message: e.response?.data?.message || '登录失败' }
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      // Even if logout request fails, clear local state
    } finally {
      authenticated.value = false
      username.value = ''
      initialized.value = false
    }
  }

  return { authenticated, username, loading, initialized, checkAuth, login, logout }
}
