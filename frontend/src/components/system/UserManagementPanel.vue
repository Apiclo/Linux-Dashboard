<template>
  <div class="p-5">
    <el-table :data="users" size="small" stripe border class="mb-3">
      <el-table-column prop="username" label="用户名" width="150" />
      <el-table-column prop="uid" label="UID" width="80" />
      <el-table-column prop="home" label="主目录" min-width="200" />
      <el-table-column prop="shell" label="Shell" width="150" />
      <el-table-column label="操作" width="200">
        <template #default="scope">
          <el-button size="small" plain @click="openPasswordDialog(scope.row.username)">改密</el-button>
          <el-button size="small" type="danger" plain @click="deleteUser(scope.row.username)" :disabled="scope.row.username === 'root'">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!users.length" description="暂无用户数据" :image-size="60" />
    <div class="flex gap-3 items-center flex-wrap">
      <el-input v-model="newUser.username" placeholder="用户名" style="width: 140px" size="small" />
      <el-input v-model="newUser.password" placeholder="密码" type="password" show-password style="width: 140px" size="small" />
      <el-input v-model="newUser.groups" placeholder="附加组(可选)" style="width: 160px" size="small" />
      <el-button size="small" type="primary" @click="addUser" :loading="userLoading">添加用户</el-button>
      <el-button size="small" @click="loadUsers">刷新</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { systemApi } from '@/api/system'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import type { UserInfo } from '@/types/api'

const toast = useToast()
const { confirm: showConfirm } = useConfirm()

const users = ref<UserInfo[]>([])
const userLoading = ref(false)
const newUser = ref({ username: '', password: '', groups: '' })

async function loadUsers() {
  try {
    const r = await systemApi.getUsers()
    users.value = r.users || []
  } catch { /* ignore */ }
}

async function addUser() {
  if (!newUser.value.username || !newUser.value.password) {
    toast.warning('请输入用户名和密码')
    return
  }
  userLoading.value = true
  try {
    const r = await systemApi.addUser(newUser.value.username, newUser.value.password, newUser.value.groups)
    toast.show(r.message || (r.success ? '已添加' : '失败'), r.success ? 'success' : 'error')
    if (r.success) { newUser.value = { username: '', password: '', groups: '' }; await loadUsers() }
  } finally {
    userLoading.value = false
  }
}

async function deleteUser(username: string) {
  const ok = await showConfirm('删除用户', `确定要删除用户 ${username} 吗？将同时删除其主目录。`, true)
  if (!ok) return
  try {
    const r = await systemApi.deleteUser(username)
    toast.show(r.message || (r.success ? '已删除' : '失败'), r.success ? 'success' : 'error')
    if (r.success) await loadUsers()
  } catch { /* ignore */ }
}

async function openPasswordDialog(username: string) {
  const password = prompt(`设置 ${username} 的新密码:`)
  if (!password) return
  try {
    const r = await systemApi.changePassword(username, password)
    toast.show(r.message || (r.success ? '密码已修改' : '失败'), r.success ? 'success' : 'error')
  } catch { /* ignore */ }
}

defineExpose({ loadUsers })
</script>
