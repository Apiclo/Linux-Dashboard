<template>
  <div>
    <div class="page-title"><el-icon><VideoCamera /></el-icon>GPU 驱动管理</div>

    <FeatureStatus :features="features" />

    <!-- Detection -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex flex-wrap justify-between items-center">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Search /></el-icon>环境检测</span>
          <div class="flex gap-3">
            <el-button size="small" plain @click="copyEnv"><el-icon class="mr-1"><CopyDocument /></el-icon>复制</el-button>
            <el-button size="small" type="warning" plain @click="checkCompat"><el-icon class="mr-1"><Shield /></el-icon>检查</el-button>
            <el-button size="small" plain @click="detect" :loading="loading"><el-icon><Refresh /></el-icon></el-button>
          </div>
        </div>
      </template>
      <div v-if="loading" class="panel-loading"><el-icon class="is-loading"><Loading /></el-icon> 正在检测 GPU 环境...</div>
      <div v-if="detectError" class="panel-error">{{ detectError }}</div>
      <template v-if="!loading && !detectError">
        <div v-if="gd.nvidia_gpus?.length > 1" class="mb-3">
          <div v-for="g in gd.nvidia_gpus" :key="g.index" class="p-2 mb-1 text-sm" style="background: var(--bg-0); border-radius: 6px">
            <strong>GPU {{ g.index }}</strong> | {{ g.gpu_name }} | {{ g.driver_version }} | {{ g.temperature }}°C | {{ g.vram_used }}/{{ g.vram_total }} MiB
          </div>
        </div>
        <div v-if="gd.gpus?.length" class="mb-3">
          <el-alert v-for="g in gd.gpus" :key="g.name" :type="g.type==='nvidia'?'success':'info'" :closable="false" class="mb-2">
            <template #title>
              <strong>{{ g.vendor }}</strong> | {{ g.name }} <span v-if="g.pci_id" style="color: var(--text-1)">| {{ g.pci_id }}</span>
            </template>
          </el-alert>
        </div>
        <el-empty v-else-if="!gd.gpus?.length" description="未检测到 GPU" :image-size="60" />
      <el-descriptions :column="2" border size="small" class="mb-3">
        <el-descriptions-item label="内核">{{ gd.kernel }}</el-descriptions-item>
        <el-descriptions-item label="头文件">{{ gd.kernel_headers || '未找到' }}</el-descriptions-item>
        <el-descriptions-item label="显示管理器">{{ gd.display_manager || '无' }}</el-descriptions-item>
        <el-descriptions-item label="AUR 助手">{{ gd.aur_helper || '无' }}</el-descriptions-item>
        <el-descriptions-item label="SecureBoot">
          <el-tag :type="gd.secure_boot?.enabled ? 'danger' : 'success'" size="small">
            {{ gd.secure_boot?.enabled ? '已启用' : '未启用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="发行版">{{ gd.distro?.pretty_name }}</el-descriptions-item>
      </el-descriptions>
      <el-alert v-if="gd.nouveau?.loaded" type="error" :closable="false" class="mt-3">
        <template #title>
          <div class="flex justify-between items-center">
            <span><strong>nouveau 已加载！</strong></span>
            <el-button size="small" type="danger" @click="doBlacklist">禁用</el-button>
          </div>
        </template>
      </el-alert>
      <el-alert v-else-if="!gd.nouveau?.blacklisted" type="warning" :closable="false" class="mt-3">
        <template #title>
          <div class="flex justify-between items-center">
            <span>nouveau 未显式禁用</span>
            <el-button size="small" type="warning" @click="doBlacklist">禁用</el-button>
          </div>
        </template>
      </el-alert>
      <el-alert v-else type="success" :closable="false" class="mt-3">
        <template #title>nouveau 已禁用</template>
      </el-alert>
      <div v-if="compat.checks?.length" class="mt-4">
        <div class="text-sm mb-2 font-semibold">兼容性检查</div>
        <el-table :data="compatRows" size="small" stripe border>
          <el-table-column prop="name" label="组件" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.iconColor === 'var(--green)' ? 'success' : row.iconColor === 'var(--yellow)' ? 'warning' : 'danger'" size="small">
                <span :style="{ color: row.iconColor, fontWeight: 'bold' }">{{ row.icon }}</span>
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="detail" label="详情" />
        </el-table>
      </div>
      </template>
    </el-card>

    <!-- nvidia-smi 实时监控 -->
    <el-card v-if="gd.nvidia_gpus?.length" shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Monitor /></el-icon>GPU 实时监控</span>
          <div class="flex gap-2">
            <el-button size="small" plain @click="refreshNvidiaSmi">刷新</el-button>
            <el-button size="small" @click="startNvidiaMonitor" :disabled="task.running">SSE 监控</el-button>
          </div>
        </div>
      </template>
      <div class="font-mono text-sm whitespace-pre-wrap" style="line-height:1.8; max-height:300px;overflow-y:auto" v-html="nvidiaSmiHtml"></div>
    </el-card>

    <!-- AMD + Intel Quick Install -->
    <el-card v-if="hasAmdGpu || hasIntelGpu" shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Cpu /></el-icon>AMD / Intel 开源驱动</span>
      </template>
      <div class="flex gap-3 flex-wrap">
        <el-card v-if="hasAmdGpu" shadow="never" class="flex-1" style="min-width: 240px; background: var(--bg-0)">
          <template #header><span class="font-semibold text-sm">AMD GPU</span></template>
          <div v-for="g in amdGpus" :key="g.name" class="text-sm mb-2" style="color: var(--text-1)">{{ g.name }}</div>
          <el-button type="primary" size="small" @click="installAmd" :disabled="task.running">安装 AMD 开源驱动</el-button>
          <el-button size="small" class="ml-2" @click="installRocm" :disabled="task.running" v-if="features.rocm_smi">安装 ROCm</el-button>
        </el-card>
        <el-card v-if="hasIntelGpu" shadow="never" class="flex-1" style="min-width: 240px; background: var(--bg-0)">
          <template #header><span class="font-semibold text-sm">Intel GPU</span></template>
          <div v-for="g in intelGpus" :key="g.name" class="text-sm mb-2" style="color: var(--text-1)">{{ g.name }}</div>
          <el-button type="primary" size="small" @click="installIntel" :disabled="task.running">安装 Intel 开源驱动</el-button>
        </el-card>
      </div>
    </el-card>

    <!-- NVIDIA Installer -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Setting /></el-icon>NVIDIA 驱动安装器</span>
      </template>
      <el-tabs v-model="tab" :lazy="false">
        <!-- Repo -->
        <el-tab-pane name="repo">
          <template #label><el-icon class="mr-1"><Box /></el-icon>仓库</template>
          <div class="flex gap-4 mb-4 items-center">
            <el-input v-model="verSearch" placeholder="搜索版本..." size="small" style="max-width: 180px" />
            <el-select v-model="repoPkg" placeholder="选择版本" filterable clearable class="flex-1" size="small">
              <el-option v-for="v in filteredVersions" :key="v.value" :label="v.label" :value="v.value" />
            </el-select>
            <el-button size="small" plain @click="loadVersions"><el-icon><Refresh /></el-icon></el-button>
          </div>
          <!-- 分组选项 -->
          <div class="grid grid-cols-12 gap-4 mb-3">
            <div v-for="group in repoOptGroups" :key="group.label" class="col-span-12 md:col-span-6">
              <div class="p-4 rounded-lg" style="background: var(--bg-0); border: 1px solid var(--border)">
                <div class="text-xs font-semibold mb-2" style="color: var(--text-2)">{{ group.label }}</div>
                <div class="flex flex-wrap gap-3">
                  <el-tooltip v-for="o in group.items" :key="o.key" :content="o.desc" placement="top">
                    <div class="flex items-center gap-2">
                      <el-checkbox v-model="opt[o.key]" />
                      <span class="text-sm cursor-pointer">{{ o.label }}</span>
                    </div>
                  </el-tooltip>
                </div>
              </div>
            </div>
          </div>
          <div class="flex gap-4 items-center">
            <el-button @click="installRepo" :disabled="!repoPkg || task.running"><el-icon class="mr-1"><Download /></el-icon>安装</el-button>
            <el-button type="danger" @click="doUninstall"><el-icon class="mr-1"><Delete /></el-icon>卸载</el-button>
          </div>
        </el-tab-pane>

        <!-- Runfile -->
        <el-tab-pane name="runfile">
          <template #label><el-icon class="mr-1"><Document /></el-icon>.run</template>
          <el-alert type="warning" :closable="false" class="mb-3">
            <template #title><strong>警告：</strong>.run 安装直接修改内核模块。</template>
          </el-alert>
          <div class="upload-zone mb-3" @click="triggerRunInput" @dragover.prevent="runDrag=true" @dragleave="runDrag=false" @drop.prevent="onRunDrop" :class="{dragover:runDrag}">
            <el-icon style="font-size: 2.5rem; color: var(--text-2)"><Upload /></el-icon>
            <div class="mt-3" style="color: var(--text-1)">点击或拖拽上传 .run 文件</div>
            <div v-if="runUpload.name" class="mt-3" style="color: var(--green)"><el-icon class="mr-1"><CircleCheck /></el-icon>{{ runUpload.name }} ({{ (runUpload.size/1024/1024).toFixed(1) }} MB)</div>
            <div v-if="runUploading" class="mt-3"><el-icon class="is-loading" :size="20"><Loading /></el-icon></div>
            <input type="file" ref="runInput" accept=".run" style="display:none" @change="onRunSelect">
          </div>
          <el-input v-model="runPath" placeholder="或直接输入路径" class="w-full mb-3" size="small" />
          <div class="flex flex-wrap gap-3 mb-3 items-center">
            <el-tooltip v-for="o in rfOpts" :key="o.key" :content="o.desc" placement="top">
              <div class="flex items-center gap-2">
                <el-checkbox v-model="rfOpt[o.key]" />
                <span class="text-sm cursor-pointer">{{ o.label }}</span>
              </div>
            </el-tooltip>
          </div>
          <el-button @click="installRun" :disabled="!runPath || task.running"><el-icon class="mr-1"><Download /></el-icon>安装 .run 驱动</el-button>
        </el-tab-pane>

        <!-- Offline -->
        <el-tab-pane name="offline">
          <template #label><el-icon class="mr-1"><Upload /></el-icon>离线包</template>
          <el-tabs v-model="offlineTab" @tab-click="onOfflineTabClick">
            <el-tab-pane name="install">
              <template #label><el-icon class="mr-1"><Download /></el-icon>安装</template>
              <div class="grid grid-cols-12">
                <div class="col-span-12 md:col-span-6">
                  <div class="upload-zone" @click="triggerOfflineInput" @dragover.prevent="olDrag=true" @dragleave="olDrag=false" @drop.prevent="onOlDrop" :class="{dragover:olDrag}">
                    <el-icon style="font-size: 2.5rem; color: var(--text-2)"><Upload /></el-icon>
                    <div class="mt-3" style="color: var(--text-1)">上传 .tar.gz 离线包</div>
                    <div v-if="olUploading" class="mt-3"><el-icon class="is-loading" :size="20"><Loading /></el-icon></div>
                    <input type="file" ref="offlineInput" accept=".tar.gz,.tgz" style="display:none" @change="onOlSelect">
                  </div>
                </div>
                <div class="col-span-12 md:col-span-6" style="max-height: 250px; overflow-y: auto">
                  <div v-for="p in offlinePkgs" :key="p.path" class="p-3 mb-2 cursor-pointer rounded-lg" style="background: var(--bg-2); border: 1px solid var(--border)" @click="olDetail=p">
                    <div class="font-semibold text-sm">{{ p.meta?.name || p.name }}</div>
                    <div class="text-xs" style="color: var(--text-1)">{{ p.package_count }} 包</div>
                  </div>
                  <div v-if="!offlinePkgs.length" style="color: var(--text-2)">暂无</div>
                </div>
              </div>
              <div v-if="olDetail" class="p-4 mt-3 rounded-lg" style="background: var(--bg-2); border: 1px solid var(--border)">
                <div class="font-semibold mb-2">包详情</div>
                <div class="mono text-sm" style="line-height: 1.8">
                  <div><strong>名称:</strong> {{ olDetail.meta?.name || 'N/A' }}</div>
                  <div><strong>版本:</strong> {{ olDetail.meta?.driver_version || 'N/A' }}</div>
                  <div><strong>镜像:</strong> {{ olDetail.meta?.target_iso || 'N/A' }}</div>
                  <div><strong>包数:</strong> {{ olDetail.package_count }}</div>
                </div>
                <div class="flex flex-col gap-2 mt-3">
                  <div class="flex items-center gap-2"><el-checkbox v-model="olOpt.use_script" /><span class="text-sm">使用 install.sh</span></div>
                  <div class="flex items-center gap-2"><el-checkbox v-model="olOpt.force" /><span class="text-sm">强制覆盖</span></div>
                </div>
                <el-button class="mt-4" @click="installOffline" :disabled="task.running"><el-icon class="mr-1"><Download /></el-icon>安装</el-button>
              </div>
            </el-tab-pane>
            <el-tab-pane name="generate">
              <template #label><el-icon class="mr-1"><MagicStick /></el-icon>生成</template>
              <div class="grid grid-cols-12">
                <div class="col-span-12 md:col-span-7">
                  <div class="p-4 rounded-lg" style="background: var(--bg-2); border: 1px solid var(--border)">
                    <div class="font-semibold mb-3">选择包</div>
                    <el-input v-model="genSearch" placeholder="搜索..." class="w-full mb-2" size="small" />
                    <div style="max-height: 300px; overflow-y: auto; border: 1px solid var(--border); border-radius: 6px; padding: 4px">
                      <el-checkbox-group v-model="genSelected">
                        <div v-for="p in filteredGenPkgs" :key="p.package" class="flex items-center gap-2 py-1 px-2 text-sm">
                          <el-checkbox :value="p.package" />
                          <span class="cursor-pointer"><span class="font-semibold">{{ p.package }}</span> <span style="color: var(--text-1)">{{ p.version }}</span></span>
                        </div>
                      </el-checkbox-group>
                    </div>
                    <div class="mt-2 text-xs" style="color: var(--text-2)">已选 {{ genSelected.length }} 个</div>
                  </div>
                </div>
                <div class="col-span-12 md:col-span-5">
                  <div class="p-4 rounded-lg" style="background: var(--bg-2); border: 1px solid var(--border)">
                    <div class="font-semibold mb-3">选项</div>
                    <div class="mb-3"><label class="block mb-1 text-sm">包名称</label><el-input v-model="genName" class="w-full" size="small" /></div>
                    <div class="mb-3"><label class="block mb-1 text-sm">适用镜像</label><el-input v-model="genIso" placeholder="如 Kylin-Desktop-V10-SP1-2403.iso" class="w-full" size="small" /></div>
                    <div class="flex items-center gap-2 mb-3"><el-checkbox v-model="genDeps" /><span class="text-sm">包含依赖</span></div>
                    <el-button class="w-full" @click="doGenerate" :disabled="!genSelected.length || task.running"><el-icon class="mr-1"><MagicStick /></el-icon>生成离线包</el-button>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <!-- CUDA -->
        <el-tab-pane name="cuda">
          <template #label><el-icon class="mr-1"><Cpu /></el-icon>CUDA</template>

          <!-- Step 1: 设置 CUDA 源 -->
          <el-card shadow="never" class="mb-3" style="background: var(--bg-1)">
            <template #header>
              <span class="font-semibold text-sm">Step 1: 设置 CUDA 软件源</span>
            </template>
            <div class="flex gap-3 mb-2 items-center">
              <el-select v-model="cudaVer" filterable allow-create clearable
                placeholder="选择或输入版本" size="small" style="max-width: 200px">
                <el-option v-for="v in cudaVersions" :key="v" :label="'CUDA ' + v" :value="v" />
              </el-select>
              <el-button size="small" @click="doSetupCudaRepo" :disabled="task.running" :loading="cudaSetupRunning">
                <el-icon class="mr-1"><Download /></el-icon>设置 CUDA 源
              </el-button>
            </div>
            <div v-if="cudaRepoReady" class="text-sm" style="color: var(--green)">
              <el-icon><CircleCheck /></el-icon> CUDA 源已配置
            </div>
            <div v-else class="text-xs" style="color: var(--text-2)">
              首次安装需先设置 NVIDIA CUDA 软件源。已配置过可跳过此步。
            </div>
          </el-card>

          <!-- Step 2: 安装 CUDA Toolkit -->
          <el-card shadow="never" style="background: var(--bg-1)">
            <template #header>
              <span class="font-semibold text-sm">Step 2: 安装 CUDA Toolkit</span>
            </template>
            <div class="mono p-2 mb-3 text-sm" style="background: var(--bg-0); border-radius: 6px">{{ gd.cuda_info || 'N/A' }}</div>
            <el-button type="primary" @click="installCuda" :disabled="task.running">
              <el-icon class="mr-1"><Download /></el-icon>安装 CUDA{{ cudaVer ? ' ' + cudaVer : '' }}
            </el-button>
          </el-card>
        </el-tab-pane>

        <!-- Custom -->
        <el-tab-pane name="custom">
          <template #label><el-icon class="mr-1"><ChatLineSquare /></el-icon>自定义</template>
          <el-input v-model="customCmd" type="textarea" :rows="3" class="w-full mb-3 font-mono mono-textarea" placeholder="输入命令..." />
          <el-button plain @click="runCustom" :disabled="!customCmd || task.running"><el-icon class="mr-1"><VideoPlay /></el-icon>执行</el-button>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Terminal -->
    <TerminalOutput
      :outputHtml="outputHtml"
      :running="task.running"
      :done="task.done"
      :exitCode="task.exitCode"
      @clear="clearOutput"
      @cancel="cancelTask"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { systemApi } from '@/api/system'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { gpuApi } from '@/api/gpu'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useSseTask } from '@/composables/useSseTask'
import type { GpuDetectData, NvidiaVersion, OfflinePackage, CompatResult, GenPackage } from '@/types/api'
import TerminalOutput from '@/components/terminal/TerminalOutput.vue'

const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['gcc','nvidia_smi','rocm_smi','sudo'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }
const { confirm: showConfirm } = useConfirm()
const { state: task, start, stop, clear, outputHtml } = useSseTask()

const loading = ref(false)
const detectError = ref('')
const gd = ref<GpuDetectData>({} as GpuDetectData)
const hasAmdGpu = computed(() => gd.value.gpus?.some((g: any) => g.vendor === 'AMD'))
const hasIntelGpu = computed(() => gd.value.gpus?.some((g: any) => g.vendor === 'Intel'))
const amdGpus = computed(() => (gd.value.gpus || []).filter((g: any) => g.vendor === 'AMD'))
const intelGpus = computed(() => (gd.value.gpus || []).filter((g: any) => g.vendor === 'Intel'))
async function installRocm() {
  if (!(await showConfirm('安装 ROCm', 'ROCm 安装包较大（数GB），将配置官方仓库并安装。继续？'))) return
  try { const r = await gpuApi.installRocm(); start(r.task_id) } catch { toast.error('ROCm 安装失败') }
}
const versions = ref<NvidiaVersion[]>([])
const compat = ref<CompatResult>({ checks: [], warnings: [], errors: [] })
const tab = ref('repo')
const offlineTab = ref('install')

const compatRows = computed(() => [
  ...compat.value.checks.map(c => ({ ...c, icon: '✓', iconColor: 'var(--green)' })),
  ...compat.value.warnings.map(c => ({ ...c, icon: '⚠', iconColor: 'var(--yellow)' })),
  ...compat.value.errors.map(c => ({ ...c, icon: '✗', iconColor: 'var(--red)' })),
])

// Repo
const verSearch = ref('')
const repoPkg = ref('')
const opt = ref<Record<string, boolean>>({ utils: true, settings: false, dkms: false, open: false, lib32: false, cuda: false, container_toolkit: false, persistenced: false, fabricmanager: false, egl: false, modeset: false })
const repoOpts = [
  { key: 'utils', label: 'nvidia-utils', desc: 'NVIDIA 驱动基础工具包' },
  { key: 'settings', label: 'nvidia-settings', desc: 'NVIDIA 图形设置工具' },
  { key: 'dkms', label: 'DKMS', desc: '内核模块自动编译支持' },
  { key: 'open', label: 'nvidia-open', desc: 'NVIDIA 开源内核模块' },
  { key: 'lib32', label: 'lib32', desc: '32 位兼容库 (游戏/Wine)' },
  { key: 'cuda', label: 'CUDA', desc: 'NVIDIA CUDA 计算平台' },
  { key: 'container_toolkit', label: 'Container Toolkit', desc: '容器 GPU 支持 (Docker/Podman)' },
  { key: 'persistenced', label: 'Persistence Daemon', desc: 'GPU 持久化守护进程' },
  { key: 'fabricmanager', label: 'Fabric Manager', desc: '多 GPU NVLink 管理器' },
  { key: 'egl', label: 'EGL 支持', desc: 'EGL 图形接口支持' },
  { key: 'modeset', label: 'DRM KMS', desc: '内核模式设置 (Wayland 需要)' },
]

const _groupDefs: Record<string, string[]> = {
  '核心驱动': ['open'],
  '基础工具': ['utils', 'settings'],
  '内核集成': ['dkms', 'modeset'],
  '兼容层': ['lib32', 'egl'],
  '计算与容器': ['cuda', 'container_toolkit'],
  '高级': ['persistenced', 'fabricmanager'],
}
const repoOptGroups = computed(() =>
  Object.entries(_groupDefs).map(([label, keys]) => ({
    label,
    items: repoOpts.filter(o => keys.includes(o.key)),
  }))
)
const filteredVersions = computed(() => {
  const q = verSearch.value.toLowerCase()
  const list = q ? versions.value.filter(v => v.package.includes(q) || v.version.includes(q)) : versions.value
  return list.map(v => ({ label: `${v.package} (${v.version})${v.source === 'aur' ? ' [AUR]' : ''}`, value: v.package }))
})

// Runfile
const runPath = ref('')
const runUpload = ref<{ name: string; size: number }>({} as any)
const runDrag = ref(false)
const runUploading = ref(false)
const runInput = ref<HTMLInputElement | null>(null)
const offlineInput = ref<HTMLInputElement | null>(null)
const rfOpt = ref<Record<string, boolean>>({ dkms: false, no_opengl: true, silent: true, stop_dm: true, blacklist: false, enable_modeset: true, no_nouveau_check: false, force: false })
const rfOpts = [
  { key: 'dkms', label: 'DKMS', desc: '内核模块自动编译' },
  { key: 'no_opengl', label: '不装 OpenGL', desc: '避免覆盖系统 OpenGL 库' },
  { key: 'silent', label: '静默安装', desc: '无交互自动完成' },
  { key: 'stop_dm', label: '停止显示管理器', desc: '安装前自动停止 DM' },
  { key: 'blacklist', label: '禁用 nouveau', desc: '自动 blacklist 开源驱动' },
  { key: 'enable_modeset', label: '启用 DRM KMS', desc: 'nvidia-drm modeset=1' },
  { key: 'no_nouveau_check', label: '跳过 nouveau 检查', desc: '忽略 nouveau 加载检测' },
  { key: 'force', label: '强制安装', desc: '忽略兼容性警告' },
]

// Offline
const offlinePkgs = ref<OfflinePackage[]>([])
const olDetail = ref<OfflinePackage | null>(null)
const olOpt = ref({ use_script: true, force: false })
const olDrag = ref(false)
const olUploading = ref(false)

// Generate
const genPkgs = ref<GenPackage[]>([])
const genSelected = ref<string[]>([])
const genSearch = ref('')
const genName = ref('')
const genIso = ref('')
const genDeps = ref(true)
const filteredGenPkgs = computed(() => {
  const q = genSearch.value.toLowerCase()
  return q ? genPkgs.value.filter(p => p.package.includes(q)) : genPkgs.value
})

// CUDA
const cudaVer = ref('')
const cudaVersions = ref<string[]>([])
const cudaSetupRunning = ref(false)
const cudaRepoReady = ref(false)

// nvidia-smi realtime
const nvidiaSmiHtml = ref('')
async function refreshNvidiaSmi() { try { nvidiaSmiHtml.value = (await gpuApi.getNvidiaSmiRealtime()).data.replace(/\n/g,'<br>') } catch { /* nvidia-smi may not be available */ } }
async function startNvidiaMonitor() { try { const r = await gpuApi.startNvidiaMonitor(); start(r.task_id) } catch { toast.error('启动失败') } }

// Custom
const customCmd = ref('')

function triggerRunInput() { runInput.value?.click() }
function triggerOfflineInput() { offlineInput.value?.click() }
function onOfflineTabClick(tab: any) { if (tab.props.name === 'generate') loadPkgList() }

async function detect() {
  loading.value = true
  detectError.value = ''
  try { gd.value = await gpuApi.detect() } catch { detectError.value = 'GPU 环境检测失败，请重试' }
  loading.value = false
}

async function loadVersions() { try { versions.value = await gpuApi.getNvidiaVersions() } catch { toast.error("加载 NVIDIA 版本列表失败") } }
async function loadCudaVersions() { try { cudaVersions.value = await gpuApi.getCudaVersions() } catch { toast.error("加载 CUDA 版本列表失败") } }
async function loadOffline() { try { offlinePkgs.value = await gpuApi.getOfflineList() } catch { toast.error("加载离线包列表失败") } }
async function loadPkgList() { try { genPkgs.value = await gpuApi.getNvidiaPackages() } catch { toast.error("加载 NVIDIA 包列表失败") } }

async function copyEnv() {
  const g = gd.value
  await navigator.clipboard.writeText(`OS: ${g.distro?.pretty_name}\nKernel: ${g.kernel}\nGPU: ${g.gpus?.map(x => x.vendor + ' ' + x.name).join(', ')}`)
  toast.success('已复制')
}

async function checkCompat() { try { compat.value = await gpuApi.getCompatibility() } catch { toast.error('失败') } }

async function doBlacklist() {
  if (!(await showConfirm('禁用 nouveau', '需要重启才能生效'))) return
  const r = await gpuApi.blacklistNouveau(); toast.show(r.message, r.success ? 'success' : 'error'); if (r.success) detect()
}

async function installRepo() {
  if (!repoPkg.value) return toast.warning('请选择版本')
  if (!(await showConfirm('安装驱动', `确定安装 ${repoPkg.value}？`))) return
  const r = await gpuApi.installRepo({ package: repoPkg.value, ...opt.value }); start(r.task_id)
}

async function doUninstall() {
  if (!(await showConfirm('卸载驱动', '确定卸载？', true))) return
  const r = await gpuApi.uninstall(); start(r.task_id)
}

async function installRun() {
  if (!runPath.value) return toast.warning('请输入路径')
  if (rfOpt.value.stop_dm) {
    const ok = await showConfirm('关闭显示管理器',
      '安装过程将关闭显示管理器（DM），所有图形界面会话将断开。\n\n确认继续？',
      true)
    if (!ok) return
  }
  const r = await gpuApi.installRunfile({ path: runPath.value, ...rfOpt.value })
  if (r.success === false) return toast.error(r.message || '失败')
  start(r.task_id)
}

async function onRunSelect(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) await uploadRun(f) }
async function onRunDrop(e: DragEvent) { runDrag.value = false; const f = e.dataTransfer?.files?.[0]; if (f) await uploadRun(f) }
async function uploadRun(f: File) {
  if (!f.name.endsWith('.run')) return toast.warning('仅支持 .run')
  runUploading.value = true
  try {
    const r = await gpuApi.uploadRunfile(f)
    if (r.success) { runPath.value = r.path; runUpload.value = { name: r.filename, size: r.size }; toast.success('上传成功') }
    else toast.error(r.message)
  } catch { toast.error('上传失败') }
  runUploading.value = false
}

async function onOlSelect(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) await uploadOl(f) }
async function onOlDrop(e: DragEvent) { olDrag.value = false; const f = e.dataTransfer?.files?.[0]; if (f) await uploadOl(f) }
async function uploadOl(f: File) {
  if (!(f.name.endsWith('.tar.gz') || f.name.endsWith('.tgz'))) return toast.warning('仅支持 .tar.gz')
  olUploading.value = true
  try {
    const r = await gpuApi.uploadOffline(f)
    if (r.success) { toast.success(`上传成功`); olDetail.value = r as any; loadOffline() }
    else toast.error(r.message)
  } catch { toast.error('上传失败') }
  olUploading.value = false
}

async function installOffline() {
  if (!olDetail.value) return toast.warning('请选择')
  const r = await gpuApi.offlineInstall({ extract_dir: olDetail.value.extract_dir || olDetail.value.path, ...olOpt.value })
  if (r.success === false) return toast.error(r.message || '失败')
  start(r.task_id)
}

async function doGenerate() {
  if (!genSelected.value.length) return
  const r = await gpuApi.generateOffline({ packages: genSelected.value, name: genName.value || undefined, target_iso: genIso.value || undefined, include_deps: genDeps.value })
  if (r.success === false) return toast.error(r.message || '失败')
  start(r.task_id)
}

async function doSetupCudaRepo() {
  cudaSetupRunning.value = true
  try {
    const r = await gpuApi.setupCudaRepo(); start(r.task_id)
    cudaRepoReady.value = true
    toast.success('CUDA 源设置任务已启动')
  } catch { toast.error('设置失败') }
  cudaSetupRunning.value = false
}

async function installCuda() { const r = await gpuApi.installCuda('network', cudaVer.value); start(r.task_id) }
async function installAmd() { const r = await gpuApi.installAmd(); start(r.task_id) }
async function installIntel() { const r = await gpuApi.installIntel(); start(r.task_id) }
async function runCustom() { if (!customCmd.value) return; const r = await gpuApi.installCustom(customCmd.value); start(r.task_id) }
function cancelTask() { stop(); toast.info('已取消') }
function clearOutput() { clear() }

onMounted(() => { detect(); loadVersions(); loadCudaVersions(); loadOffline(); fetchFeatures() })
</script>

<style scoped>
.mono { font-family: 'JetBrains Mono', monospace; }
</style>
