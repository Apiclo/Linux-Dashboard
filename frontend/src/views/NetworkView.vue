<template>
  <div>
    <div class="page-title"><el-icon><Connection /></el-icon>网络设置</div>

    <el-collapse v-model="activeCollapse">
      <!-- 网络接口 -->
      <el-collapse-item name="interfaces">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Link /></el-icon>网络接口</span>
        </template>
        <div class="p-5">
          <el-button size="small" plain class="mb-3" @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
          <el-table :data="interfaces" size="small" stripe border v-loading="loading">
            <el-table-column prop="name" label="接口">
              <template #default="scope"><span class="mono">{{ scope.row.name }}</span></template>
            </el-table-column>
            <el-table-column prop="is_up" label="状态">
              <template #default="scope"><el-tag :type="scope.row.is_up ? 'success' : 'danger'">{{ scope.row.is_up ? 'UP' : 'DOWN' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="IPv4">
              <template #default="scope"><span class="mono text-sm">{{ scope.row.ipv4.join(', ') }}</span></template>
            </el-table-column>
            <el-table-column label="IPv6">
              <template #default="scope"><span class="mono text-sm">{{ scope.row.ipv6.slice(0, 2).join(', ') }}</span></template>
            </el-table-column>
            <el-table-column label="MAC">
              <template #default="scope"><span class="mono text-sm">{{ scope.row.mac }}</span></template>
            </el-table-column>
            <el-table-column label="速度">
              <template #default="scope">{{ scope.row.speed ? scope.row.speed + ' Mbps' : '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="scope">
                <el-button size="small" type="success" text @click="ifaceAction(scope.row.name, 'up')">启用</el-button>
                <el-button size="small" type="danger" text @click="ifaceAction(scope.row.name, 'down')">禁用</el-button>
                <el-button size="small" type="warning" text @click="ifaceAction(scope.row.name, 'restart')">重启</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-collapse-item>

      <!-- 防火墙 -->
      <el-collapse-item name="firewall">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Shield /></el-icon>防火墙</span>
        </template>
        <div class="p-5">
        <div class="mb-3 text-sm">
          <span class="font-semibold">{{ fw.name }}</span>:
          <span :style="{ color: fw.status?.includes('running') ? 'var(--green)' : 'var(--yellow)' }">{{ fw.status }}</span>
        </div>
        <div class="flex gap-3 mb-3 items-center flex-wrap">
          <el-button size="small" type="primary" plain @click="showAllowPort = true"><el-icon class="mr-1"><CirclePlus /></el-icon>允许端口</el-button>
          <el-button size="small" type="danger" plain @click="showDenyPort = true"><el-icon class="mr-1"><Remove /></el-icon>禁止端口</el-button>
          <el-button size="small" plain @click="viewRules"><el-icon class="mr-1"><Document /></el-icon>查看规则</el-button>
        </div>
        <div class="flex gap-3 mb-3 items-center">
          <el-input v-model="fwCmd" placeholder="如: ufw status" class="flex-1" size="small" @keyup.enter="runFwCmd" />
          <el-button size="small" plain @click="runFwCmd">执行</el-button>
        </div>
        <div class="terminal">{{ fwOutput || '输入命令后执行' }}</div>
        </div>
      </el-collapse-item>

      <!-- DNS 配置 -->
      <el-collapse-item name="dns">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Share /></el-icon>DNS 配置</span>
        </template>
        <div class="p-5">
        <div class="mb-4">
          <div class="font-semibold text-sm mb-2">当前 DNS 服务器</div>
          <div class="mono p-3 text-sm" style="background: var(--bg-0); border-radius: 6px; min-height: 60px">
            <div v-for="d in dns" :key="d">nameserver {{ d }}</div>
            <div v-if="!dns.length" style="color: var(--text-2)">未配置</div>
          </div>
        </div>
        <div class="font-semibold text-sm mb-2">修改 DNS</div>
        <el-form label-width="100px" size="small">
          <el-form-item label="主 DNS">
            <el-input v-model="dnsPrimary" placeholder="如 8.8.8.8" style="width: 100%; max-width: 220px" />
          </el-form-item>
          <el-form-item label="备 DNS">
            <el-input v-model="dnsBackup" placeholder="如 8.8.4.4" style="width: 100%; max-width: 220px" />
          </el-form-item>
          <el-form-item>
            <el-button size="small" type="primary" :loading="dnsSaving" @click="saveDns">保存</el-button>
          </el-form-item>
        </el-form>
        </div>
      </el-collapse-item>

      <!-- 端口监听 -->
      <el-collapse-item name="ports">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Monitor /></el-icon>端口监听</span>
        </template>
        <div class="p-5">
          <el-button size="small" plain class="mb-3" :loading="portsLoading" @click="loadPorts"><el-icon><Refresh /></el-icon>刷新</el-button>
          <el-table :data="ports" size="small" stripe border max-height="400px">
            <el-table-column prop="protocol" label="协议" width="80" />
            <el-table-column prop="local_address" label="本地地址" />
            <el-table-column prop="process" label="进程" />
          </el-table>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- 允许端口弹窗 -->
    <el-dialog v-model="showAllowPort" title="允许端口" width="400px">
      <el-form label-width="80px">
        <el-form-item label="端口号">
          <el-input v-model="portForm.port" placeholder="如: 8080" />
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="portForm.protocol" class="w-full">
            <el-option label="TCP" value="tcp" />
            <el-option label="UDP" value="udp" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAllowPort = false">取消</el-button>
        <el-button type="primary" @click="allowPort">确定</el-button>
      </template>
    </el-dialog>

    <!-- 禁止端口弹窗 -->
    <el-dialog v-model="showDenyPort" title="禁止端口" width="400px">
      <el-form label-width="80px">
        <el-form-item label="端口号">
          <el-input v-model="portForm.port" placeholder="如: 8080" />
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="portForm.protocol" class="w-full">
            <el-option label="TCP" value="tcp" />
            <el-option label="UDP" value="udp" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDenyPort = false">取消</el-button>
        <el-button type="danger" @click="denyPort">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { networkApi } from '@/api/network'
import { useToast } from '@/composables/useToast'
import type { NetworkInterface, PortInfo } from '@/types/api'

const toast = useToast()
const loading = ref(false)
const activeCollapse = ref(['interfaces', 'firewall', 'dns'])
const interfaces = ref<NetworkInterface[]>([])
const dns = ref<string[]>([])
const fw = ref({ name: '-', status: '-' })
const fwCmd = ref('')
const fwOutput = ref('')

// DNS config
const dnsPrimary = ref('')
const dnsBackup = ref('')
const dnsSaving = ref(false)

// Ports
const ports = ref<PortInfo[]>([])
const portsLoading = ref(false)

// Port form
const showAllowPort = ref(false)
const showDenyPort = ref(false)
const portForm = ref({ port: '', protocol: 'tcp' })

async function load() {
  loading.value = true
  try {
    const [ifaces, dnsRes, fwRes] = await Promise.all([networkApi.getInterfaces(), networkApi.getDns(), networkApi.getFirewall()])
    interfaces.value = ifaces; dns.value = dnsRes.dns; fw.value = fwRes
  } catch { toast.error('加载失败') }
  finally { loading.value = false }
}

async function runFwCmd() {
  if (!fwCmd.value.trim()) return
  try {
    const res = await networkApi.runFwCmd(fwCmd.value)
    fwOutput.value = res.message || '无输出'
    if (!res.success) toast.warning(res.message || '失败')
  } catch (e: any) { fwOutput.value = '错误: ' + (e.response?.data?.message || e.message) }
}

async function ifaceAction(name: string, action: string) {
  try {
    const res = await networkApi.interfaceAction(name, action as 'up' | 'down' | 'restart')
    if (res.success) { toast.success(`接口 ${name} ${action === 'up' ? '已启用' : action === 'down' ? '已禁用' : '已重启'}`); load() }
    else toast.warning(res.message || '操作失败')
  } catch (e: any) { toast.error(e.response?.data?.message || '操作失败') }
}

async function viewRules() {
  try {
    const res = await networkApi.runFwCmd('ufw status verbose')
    fwOutput.value = res.message || '无输出'
  } catch (e: any) { fwOutput.value = '错误: ' + (e.response?.data?.message || e.message) }
}

async function allowPort() {
  if (!portForm.value.port) { toast.warning('请输入端口号'); return }
  try {
    const res = await networkApi.fwAllow(portForm.value.port, portForm.value.protocol)
    if (res.success) { toast.success('端口已允许'); showAllowPort.value = false; portForm.value.port = ''; fwOutput.value = res.message || '' }
    else toast.warning(res.message || '操作失败')
  } catch (e: any) { toast.error(e.response?.data?.message || '操作失败') }
}

async function denyPort() {
  if (!portForm.value.port) { toast.warning('请输入端口号'); return }
  try {
    const res = await networkApi.fwDeny(portForm.value.port, portForm.value.protocol)
    if (res.success) { toast.success('端口已禁止'); showDenyPort.value = false; portForm.value.port = ''; fwOutput.value = res.message || '' }
    else toast.warning(res.message || '操作失败')
  } catch (e: any) { toast.error(e.response?.data?.message || '操作失败') }
}

async function saveDns() {
  const servers = [dnsPrimary.value, dnsBackup.value].filter(Boolean)
  if (!servers.length) { toast.warning('请至少填写一个 DNS 地址'); return }
  dnsSaving.value = true
  try {
    const res = await networkApi.setDns(servers)
    if (res.success) { toast.success('DNS 已更新'); load() }
    else toast.warning(res.message || '更新失败')
  } catch (e: any) { toast.error(e.response?.data?.message || '更新失败') }
  finally { dnsSaving.value = false }
}

async function loadPorts() {
  portsLoading.value = true
  try {
    const res = await networkApi.getPorts()
    ports.value = res.ports
  } catch { toast.error('加载端口失败') }
  finally { portsLoading.value = false }
}

onMounted(load)
</script>

<style scoped>
.mono { font-family: 'JetBrains Mono', monospace; }
</style>
