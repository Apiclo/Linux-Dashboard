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

    <!-- 改密弹窗 -->
    <el-dialog v-model="pwDialogVisible" title="修改密码" width="380px">
      <el-form label-width="80px" size="small">
        <el-form-item label="用户"><strong>{{ pwUser }}</strong></el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwNew" type="password" show-password placeholder="输入新密码" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="pwConfirm" type="password" show-password placeholder="再次输入" @keyup.enter="doChangePassword" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doChangePassword" :disabled="!pwNew">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
  } catch { toast.error("用户列表加载失败") }
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
  } catch { toast.error("删除用户失败") }
}

const pwDialogVisible = ref(false)
const pwUser = ref('')
const pwNew = ref('')
const pwConfirm = ref('')

function openPasswordDialog(username: string) {
  pwUser.value = username; pwNew.value = ''; pwConfirm.value = ''
  pwDialogVisible.value = true
}

async function doChangePassword() {
  if (!pwNew.value) return toast.warning('请输入密码')
  if (pwNew.value !== pwConfirm.value) return toast.warning('两次密码不一致')
  try {
    const r = await systemApi.changePassword(pwUser.value, pwNew.value)
    toast.show(r.message || (r.success ? '密码已修改' : '失败'), r.success ? 'success' : 'error')
    if (r.success) pwDialogVisible.value = false
  } catch { toast.error("密码修改失败") }
}

defineExpose({ loadUsers })
onMounted(loadUsers)
</script>
