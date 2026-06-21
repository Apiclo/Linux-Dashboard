<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">
          <el-icon :size="24" color="#fff"><Setting /></el-icon>
        </div>
        <h2 class="login-title">Linux Toolbox</h2>
        <p class="login-subtitle">使用系统账号登录管理面板</p>
      </div>

      <el-alert v-if="error" type="error" :closable="false" class="login-alert" show-icon>{{ error }}</el-alert>

      <el-form @submit.prevent="handleLogin" class="login-form">
        <el-form-item label="用户名">
          <el-input v-model="username" placeholder="root" size="default" @keyup.enter="handleLogin" autofocus :disabled="loading" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password placeholder="输入密码" size="default" @keyup.enter="handleLogin" :disabled="loading" :prefix-icon="Lock" />
        </el-form-item>
        <el-button type="primary" size="default" class="login-btn" @click="handleLogin" :loading="loading" :disabled="!username || !password">
          {{ loading ? '登录中...' : '登录' }}
        </el-button>
      </el-form>

      <div class="login-footer">
        <span>PAM 系统认证 · 所有操作记录审计日志</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { login, loading } = useAuth()
const username = ref('')
const password = ref('')
const error = ref('')

// Clear error when user modifies input
watch([username, password], () => { error.value = '' })

async function handleLogin() {
  if (!username.value || !password.value) return
  error.value = ''
  const res = await login(username.value, password.value)
  if (res.success) {
    router.push('/system')
  } else {
    error.value = res.message
    password.value = ''
  }
}
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-0);
  padding: 20px;
}
.login-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 40px;
  width: 420px;
  max-width: 100%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-logo {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--accent), #a855f7);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}
.login-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-0);
  margin: 0 0 6px;
  letter-spacing: -0.5px;
}
.login-subtitle {
  font-size: 14px;
  color: var(--text-1);
  margin: 0;
}
.login-alert {
  margin-bottom: 20px;
}
.login-form {
  margin-bottom: 0;
}
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-md);
  margin-top: 8px;
}
.login-footer {
  text-align: center;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}
.login-footer span {
  font-size: 12px;
  color: var(--text-2);
}
</style>
