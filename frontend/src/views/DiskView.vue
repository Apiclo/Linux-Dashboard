<template>
  <div>
    <div class="page-title"><el-icon><Coin /></el-icon>磁盘管理</div>

    <!-- 块设备列表 -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-2 font-semibold"><el-icon><Coin /></el-icon>块设备</span>
          <el-button size="small" plain :icon="Refresh" @click="load">刷新</el-button>
        </div>
      </template>
      <el-table :data="flatDevices" size="small" stripe border max-height="400">
        <el-table-column prop="name" label="设备名" min-width="140">
          <template #default="{ row }">
            <span class="font-mono" :class="row.isChild ? 'text-gray-400' : 'font-bold text-blue-400'">
              {{ row.isChild ? '  └ ' : '' }}/dev/{{ row.name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="size" label="大小" width="100" />
        <el-table-column prop="type" label="类型" width="80" />
        <el-table-column prop="fstype" label="文件系统" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.fstype" size="small" type="info">{{ row.fstype }}</el-tag>
            <span v-else style="color: var(--text-2)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="mountpoint" label="挂载点" min-width="140">
          <template #default="{ row }">
            <span v-if="row.mountpoint" class="text-green-500">{{ row.mountpoint }}</span>
            <span v-else style="color: var(--text-2)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="uuid" label="UUID" min-width="200">
          <template #default="{ row }">
            <span v-if="row.uuid" class="font-mono text-xs" style="color: var(--text-2)">{{ row.uuid }}</span>
            <span v-else style="color: var(--text-2)">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 磁盘使用量 -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <span class="flex items-center gap-2 font-semibold"><el-icon><Histogram /></el-icon>磁盘使用</span>
      </template>
      <div v-if="usageLines.length">
        <div v-for="line in usageLines" :key="line.mount" class="mb-3">
          <div class="flex items-center justify-between mb-1">
            <span class="font-mono text-sm">{{ line.mount }}</span>
            <span class="text-xs" style="color: var(--text-2)">{{ line.used }} / {{ line.total }} ({{ line.percent }}%)</span>
          </div>
          <el-progress
            :percentage="line.percent"
            :color="line.percent > 90 ? '#f56c6c' : line.percent > 70 ? '#e6a23c' : '#67c23a'"
            :stroke-width="18"
            :text-inside="true"
          />
        </div>
      </div>
      <pre v-else class="m-0 text-sm" style="color: var(--text-1); background: var(--bg-0); padding: 10px; border-radius: 6px">{{ usage || '加载中...' }}</pre>
    </el-card>

    <!-- 挂载 / 卸载 -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <span class="flex items-center gap-2 font-semibold"><el-icon><Top /></el-icon>挂载 / 卸载</span>
      </template>
      <el-form label-width="80px">
        <el-form-item label="设备">
          <el-input v-model="mountDevice" placeholder="/dev/sdb1" size="small" />
        </el-form-item>
        <el-form-item label="挂载点">
          <el-input v-model="mountPoint" placeholder="/mnt/data" size="small" />
        </el-form-item>
        <el-form-item label="文件系统">
          <el-select v-model="mountFs" placeholder="自动" clearable size="small" class="w-full">
            <el-option v-for="item in fsOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <div class="flex gap-3 items-center">
            <el-button size="small" :icon="Top" @click="doMount">挂载</el-button>
            <el-button type="danger" size="small" :icon="Bottom" @click="doUmount">卸载</el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- fstab -->
    <el-card shadow="never" class="mb-5">
      <template #header>
        <span class="flex items-center gap-2 font-semibold"><el-icon><EditPen /></el-icon>/etc/fstab</span>
      </template>
      <el-input v-model="fstab" type="textarea" :rows="15" class="w-full mb-3 mono" style="font-size: 12px" />
      <el-button size="small" :icon="FolderChecked" @click="saveFstab">保存</el-button>
    </el-card>

    <!-- RAID 管理 -->
    <el-collapse v-model="raidCollapse" class="mb-5">
      <el-collapse-item name="raid">
        <template #title>
          <span class="flex items-center gap-2 font-semibold"><el-icon><Coin /></el-icon>RAID 管理</span>
        </template>
        <div class="p-5">
          <!-- 已有 RAID 数组 -->
          <div class="flex items-center justify-between mb-3">
            <span class="font-semibold">已有 RAID 数组</span>
            <el-button size="small" plain :icon="Refresh" @click="loadRaid">刷新</el-button>
          </div>
          <el-table :data="raidArrays" size="small" stripe border class="mb-3" v-if="raidArrays.length">
            <el-table-column prop="name" label="名称" min-width="120">
              <template #default="{ row }"><span class="font-mono font-bold text-blue-400">{{ row.name }}</span></template>
            </el-table-column>
            <el-table-column prop="level" label="级别" width="80" />
            <el-table-column label="设备" min-width="200">
              <template #default="{ row }"><span class="font-mono text-xs">{{ row.devices.join(', ') }}</span></template>
            </el-table-column>
            <el-table-column prop="status" label="状态" min-width="200">
              <template #default="{ row }"><span class="text-xs" style="color: var(--text-2)">{{ row.status || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <el-button size="small" plain @click="viewRaidDetail(row.name)">详情</el-button>
                <el-button size="small" type="warning" plain @click="manageRaidAction('/dev/' + row.name, 'stop')">停止</el-button>
                <el-button size="small" type="danger" plain @click="manageRaidAction('/dev/' + row.name, 'remove')">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="text-sm mb-4" style="color: var(--text-2)">暂无 RAID 数组</div>

          <!-- 创建 RAID -->
          <el-divider content-position="left">创建 RAID</el-divider>
          <el-form label-width="80px" size="small">
            <el-form-item label="RAID 级别">
              <el-select v-model="raidForm.level" style="width: 160px">
                <el-option label="RAID 0 (条带)" value="0" />
                <el-option label="RAID 1 (镜像)" value="1" />
                <el-option label="RAID 5 (分布式奇偶)" value="5" />
                <el-option label="RAID 6 (双重奇偶)" value="6" />
                <el-option label="RAID 10 (镜像+条带)" value="10" />
              </el-select>
            </el-form-item>
            <el-form-item label="数组名称">
              <el-input v-model="raidForm.name" placeholder="md0 (可选)" style="max-width: 240px" />
            </el-form-item>
            <el-form-item label="选择设备">
              <div v-if="raidDevices.length" class="flex flex-wrap gap-3">
                <el-checkbox
                  v-for="dev in raidDevices"
                  :key="dev.path"
                  :label="`${dev.path} (${dev.size})`"
                  :model-value="raidForm.devices.includes(dev.path)"
                  @change="(v: any) => toggleRaidDevice(dev.path, v)"
                />
              </div>
              <span v-else class="text-sm" style="color: var(--text-2)">无可用设备</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="createRaidArray" :loading="raidCreating">创建 RAID</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- RAID Detail Dialog -->
    <el-dialog v-model="raidDetailVisible" title="RAID 详情" width="600px">
      <pre class="text-xs font-mono whitespace-pre-wrap" style="background: var(--bg-1); padding: 12px; border-radius: 6px; max-height: 400px; overflow: auto">{{ raidDetailContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, Top, Bottom, Histogram, EditPen, FolderChecked } from '@element-plus/icons-vue'
import { diskApi } from '@/api/disk'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import type { BlockDevice } from '@/types/api'

const toast = useToast()
const { confirm: showConfirm } = useConfirm()
const devices = ref<BlockDevice[]>([])
const usage = ref('')
const fstab = ref('')
const mountDevice = ref('')
const mountPoint = ref('')
const mountFs = ref('')

const fsOptions = [
  { label: 'ext4', value: 'ext4' },
  { label: 'xfs', value: 'xfs' },
  { label: 'btrfs', value: 'btrfs' },
  { label: 'ntfs', value: 'ntfs' },
  { label: 'vfat', value: 'vfat' },
  { label: 'tmpfs', value: 'tmpfs' },
  { label: 'nfs', value: 'nfs' },
  { label: 'cifs', value: 'cifs' },
]

interface FlatDevice {
  name: string
  size: string
  type: string
  fstype: string
  mountpoint: string
  uuid: string
  isChild: boolean
}

const flatDevices = computed<FlatDevice[]>(() => {
  const result: FlatDevice[] = []
  for (const d of devices.value) {
    result.push({
      name: d.name,
      size: d.size,
      type: d.type || 'disk',
      fstype: d.fstype,
      mountpoint: d.mountpoint,
      uuid: d.uuid,
      isChild: false,
    })
    for (const c of d.children || []) {
      result.push({
        name: c.name,
        size: c.size,
        type: c.type || 'part',
        fstype: c.fstype,
        mountpoint: c.mountpoint,
        uuid: c.uuid,
        isChild: true,
      })
    }
  }
  return result
})

interface UsageLine {
  mount: string
  used: string
  total: string
  percent: number
}

const usageLines = computed<UsageLine[]>(() => {
  if (!usage.value) return []
  const lines: UsageLine[] = []
  for (const line of usage.value.split('\n')) {
    const parts = line.trim().split(/\s+/)
    if (parts.length >= 5 && parts[4] !== 'Use%') {
      const pct = parseInt(parts[4])
      if (!isNaN(pct)) {
        lines.push({
          mount: parts[5] || parts[0],
          used: parts[2],
          total: parts[1],
          percent: pct,
        })
      }
    }
  }
  return lines
})

async function load() {
  try {
    const [devs, u, f] = await Promise.all([diskApi.getDevices(), diskApi.getUsage(), diskApi.getFstab()])
    devices.value = devs; usage.value = u.usage; fstab.value = f.content
  } catch { toast.error('加载失败') }
}

async function doMount() {
  if (!mountDevice.value || !mountPoint.value) return toast.warning('请输入设备和挂载点')
  if (!(await showConfirm('挂载', `确定挂载 ${mountDevice.value} → ${mountPoint.value}？`))) return
  const r = await diskApi.mount(mountDevice.value, mountPoint.value, mountFs.value)
  toast.show(r.message, r.success ? 'success' : 'error'); if (r.success) load()
}

async function doUmount() {
  const t = mountDevice.value || mountPoint.value
  if (!t) return toast.warning('请输入设备或挂载点')
  if (!(await showConfirm('卸载', `确定卸载 ${t}？`))) return
  const r = await diskApi.umount(t)
  toast.show(r.message, r.success ? 'success' : 'error'); if (r.success) load()
}

async function saveFstab() {
  if (!(await showConfirm('保存 fstab', '错误的配置可能导致无法启动，确定？'))) return
  const r = await diskApi.saveFstab(fstab.value)
  toast.show(r.success ? '已保存' : '失败', r.success ? 'success' : 'error')
}

// ── RAID ──
const raidCollapse = ref<string[]>([])
const raidArrays = ref<any[]>([])
const raidDevices = ref<any[]>([])
const raidCreating = ref(false)
const raidForm = ref({ level: '1', name: '', devices: [] as string[] })
const raidDetailVisible = ref(false)
const raidDetailContent = ref('')

async function loadRaid() {
  try {
    const [arraysRes, devsRes] = await Promise.all([diskApi.getRaidArrays(), diskApi.getRaidDevices()])
    raidArrays.value = arraysRes.arrays || []
    raidDevices.value = devsRes.devices || []
  } catch { /* ignore */ }
}

function toggleRaidDevice(path: string, checked: boolean) {
  if (checked) {
    if (!raidForm.value.devices.includes(path)) raidForm.value.devices.push(path)
  } else {
    raidForm.value.devices = raidForm.value.devices.filter(d => d !== path)
  }
}

async function createRaidArray() {
  if (raidForm.value.devices.length < 2) return toast.warning('至少选择 2 个设备')
  if (!(await showConfirm('创建 RAID', `确定创建 RAID ${raidForm.value.level}，设备: ${raidForm.value.devices.join(', ')}？`))) return
  raidCreating.value = true
  try {
    const r = await diskApi.createRaid(raidForm.value.level, raidForm.value.devices, raidForm.value.name)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) { raidForm.value = { level: '1', name: '', devices: [] }; await loadRaid() }
  } finally {
    raidCreating.value = false
  }
}

async function manageRaidAction(device: string, action: string) {
  const label = action === 'stop' ? '停止' : '移除'
  if (!(await showConfirm(label, `确定${label} ${device}？`))) return
  const r = await diskApi.manageRaid(device, action)
  toast.show(r.message, r.success ? 'success' : 'error')
  if (r.success) await loadRaid()
}

async function viewRaidDetail(name: string) {
  try {
    const r = await diskApi.getRaidDetail('/dev/' + name)
    raidDetailContent.value = r.success ? r.detail : (r as any).message || '获取失败'
    raidDetailVisible.value = true
  } catch { toast.error('获取详情失败') }
}

onMounted(() => { load(); loadRaid() })
</script>

<style scoped>
.mono { font-family: 'JetBrains Mono', monospace; }
</style>
