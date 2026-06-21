<template>
  <div>
    <div class="page-title"><el-icon><Coin /></el-icon>磁盘管理
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新" />
    </div>

    <FeatureStatus :features="features" />

    <!-- 块设备列表 -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Coin /></el-icon>块设备</span>
          <el-button size="small" plain :icon="Refresh" @click="load">刷新</el-button>
        </div>
      </template>
      <div v-if="devicesLoading" class="panel-loading"><el-icon class="is-loading"><Loading /></el-icon> 加载磁盘信息...</div>
      <el-table v-else-if="flatDevices.length" :data="sortedDevices" size="small" stripe border max-height="400" @sort-change="onDeviceSort">
        <el-table-column prop="name" label="设备名" min-width="140" sortable="custom">
          <template #default="{ row }">
            <span class="font-mono" :style="{ color: row.isChild ? 'var(--text-2)' : 'var(--accent)', fontWeight: row.isChild ? 'normal' : 'bold' }">
              <span v-if="row.isChild" style="color: var(--border)">├─ </span>/dev/{{ row.name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="size" label="大小" width="100" sortable="custom" />
        <el-table-column prop="type" label="类型" width="80" />
        <el-table-column prop="fstype" label="文件系统" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.fstype" size="small" type="info">{{ row.fstype }}</el-tag>
            <span v-else style="color: var(--text-2)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="mountpoint" label="挂载点" min-width="140">
          <template #default="{ row }">
            <span v-if="row.mountpoint" style="color: var(--green)">{{ row.mountpoint }}</span>
            <span v-else style="color: var(--text-2)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="uuid" label="UUID" min-width="200">
          <template #default="{ row }">
            <span v-if="row.uuid" class="font-mono text-xs" style="color: var(--text-2)">{{ row.uuid }}</span>
            <span v-else style="color: var(--text-2)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button
              v-if="!row.mountpoint && row.type === 'part'"
              size="small"
              type="danger"
              plain
              @click="openFormatDialog(row)"
            >格式化</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="未检测到块设备" :image-size="60" />
    </el-card>

    <!-- 磁盘使用量 -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Histogram /></el-icon>磁盘使用</span>
      </template>
      <el-table v-if="usageDevices.length" :data="usageDevices" size="small" stripe border>
        <el-table-column prop="target" label="挂载点" min-width="140">
          <template #default="{ row }">
            <span class="font-mono text-sm">{{ row.target }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="设备" min-width="180">
          <template #default="{ row }">
            <span class="font-mono text-xs">{{ row.source }}</span>
          </template>
        </el-table-column>
        <el-table-column label="使用率" min-width="280">
          <template #default="{ row }">
            <div class="flex items-center gap-3">
              <el-progress
                class="flex-1"
                :percentage="parsePercent(row.use_pct)"
                :color="parsePercent(row.use_pct) > 90 ? '#f56c6c' : parsePercent(row.use_pct) > 70 ? '#e6a23c' : '#67c23a'"
                :stroke-width="16"
                :text-inside="true"
              />
              <span class="text-xs" style="color: var(--text-2); white-space: nowrap; min-width: 90px; text-align: right">
                {{ formatBytes(row.used_bytes) }} / {{ formatBytes(row.size_bytes) }}
              </span>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <pre v-else-if="usage" class="m-0 text-sm" style="color: var(--text-1); background: var(--bg-0); padding: 10px; border-radius: 6px">{{ usage }}</pre>
      <div v-else class="text-sm text-center py-5" style="color: var(--text-2)">加载中...</div>
    </el-card>

    <!-- 挂载 / 卸载 -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Top /></el-icon>挂载 / 卸载</span>
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
          <div class="flex gap-4 items-center">
            <el-button size="small" :icon="Top" @click="doMount">挂载</el-button>
            <el-button type="danger" size="small" :icon="Bottom" @click="doUmount">卸载</el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- fstab -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><EditPen /></el-icon>/etc/fstab</span>
      </template>
      <el-empty v-if="!fstab && !devicesLoading" description="fstab 文件为空或未加载" :image-size="60" />
      <template v-else>
        <el-input v-model="fstab" type="textarea" :rows="15" class="w-full mb-3 mono mono-textarea" />
        <el-button size="small" :icon="FolderChecked" @click="saveFstab">保存</el-button>
      </template>
    </el-card>

    <!-- RAID 管理 -->
    <el-collapse v-model="raidCollapse" class="mb-6">
      <el-collapse-item name="raid">
        <template #title>
          <span class="flex items-center gap-3 font-semibold"><el-icon><Coin /></el-icon>RAID 管理</span>
        </template>
        <div class="p-5">
          <!-- 已有 RAID 数组 -->
          <div class="flex items-center justify-between mb-3">
            <span class="font-semibold">已有 RAID 数组</span>
            <el-button size="small" plain :icon="Refresh" @click="loadRaid">刷新</el-button>
          </div>
          <el-table :data="raidArrays" size="small" stripe border class="mb-3" v-if="raidArrays.length">
            <el-table-column prop="name" label="名称" min-width="120">
              <template #default="{ row }"><span class="font-mono" style="color: var(--accent); font-weight: bold">{{ row.name }}</span></template>
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

    <!-- ═══════════ LVM 管理 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Coin /></el-icon>LVM 管理</span>
          <el-button size="small" plain @click="loadLvm">刷新</el-button>
        </div>
      </template>
      <div v-if="lvm.installed === false" class="text-sm" style="color: var(--text-2)">LVM 未安装 (apt install lvm2)</div>
      <template v-else>
        <div v-if="lvm.pvs?.length" class="mb-3">
          <div class="font-semibold text-sm mb-1">物理卷 (PV)</div>
          <el-table :data="lvm.pvs" size="small" stripe border>
            <el-table-column prop="name" label="设备" min-width="160"><template #default="{row}"><span class="font-mono text-sm">{{row.name}}</span></template></el-table-column>
            <el-table-column prop="size" label="大小" width="80" />
            <el-table-column prop="free" label="可用" width="80" />
            <el-table-column prop="vg" label="所属 VG" width="100" />
          </el-table>
        </div>
        <div v-if="lvm.vgs?.length" class="mb-3">
          <div class="font-semibold text-sm mb-1">卷组 (VG)</div>
          <el-table :data="lvm.vgs" size="small" stripe border>
            <el-table-column prop="name" label="名称" width="100" />
            <el-table-column prop="size" label="大小" width="80" />
            <el-table-column prop="free" label="可用" width="80" />
            <el-table-column prop="pv_count" label="PV数" width="60" />
            <el-table-column prop="lv_count" label="LV数" width="60" />
          </el-table>
        </div>
        <div v-if="lvm.lvs?.length" class="mb-3">
          <div class="font-semibold text-sm mb-1">逻辑卷 (LV)</div>
          <el-table :data="lvm.lvs" size="small" stripe border>
            <el-table-column prop="name" label="名称" width="120" />
            <el-table-column prop="vg" label="VG" width="80" />
            <el-table-column prop="size" label="大小" width="80" />
            <el-table-column prop="data_percent" label="使用率" width="70" />
            <el-table-column label="类型" width="80">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ lvTypeLabel(row.attr) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{row}">
                <el-button size="small" plain @click="showLvResize(row)">扩容</el-button>
                <el-button size="small" type="danger" plain @click="doRemoveLv(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <!-- 快速创建 LV -->
        <el-divider content-position="left">创建逻辑卷</el-divider>
        <div class="flex gap-4 items-center flex-wrap">
          <el-input v-model="lvForm.name" placeholder="LV名称" size="small" style="width:120px" />
          <el-select v-model="lvForm.vg" placeholder="选择VG" size="small" style="width:120px" clearable>
            <el-option v-for="v in lvm.vgs" :key="v.name" :label="v.name" :value="v.name" />
          </el-select>
          <el-input v-model="lvForm.size" placeholder="大小 (如 10G)" size="small" style="width:120px" />
          <el-button size="small" type="primary" @click="doCreateLv">创建</el-button>
        </div>
      </template>
    </el-card>

    <!-- ═══════════ Btrfs / 文件系统工具 ═══════════ -->
    <div class="grid grid-cols-12 gap-5 mb-5">
      <div class="col-span-12 md:col-span-6">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="flex items-center gap-3 font-semibold"><el-icon><FolderOpened /></el-icon>Btrfs</span>
              <el-button size="small" plain @click="loadBtrfs">刷新</el-button>
            </div>
          </template>
          <div v-if="btrfs.installed === false" class="text-sm" style="color: var(--text-2)">btrfs-progs 未安装</div>
          <template v-else>
            <div v-if="btrfs.subvolumes?.length" class="mb-3">
              <div class="font-semibold text-sm mb-1">子卷</div>
              <el-table :data="btrfs.subvolumes" size="small" stripe border max-height="200">
                <el-table-column prop="id" label="ID" width="60" />
                <el-table-column prop="path" label="路径" min-width="160"><template #default="{row}"><span class="font-mono text-sm">{{row.path}}</span></template></el-table-column>
                <el-table-column label="标记" width="80">
                  <template #default="{row}">
                    <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
                    <span v-else style="color: var(--text-2)">—</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <div class="flex gap-2 flex-wrap">
              <el-input v-model="btrfsSubvol" placeholder="子卷路径" size="small" style="width:200px" />
              <el-button size="small" @click="doCreateSubvol">创建子卷</el-button>
              <el-button size="small" type="warning" @click="doScrub">Scrub</el-button>
            </div>
            <el-divider content-position="left" class="!my-2">维护</el-divider>
            <div class="flex gap-3 items-center flex-wrap">
              <el-input v-model="btrfsMount" placeholder="挂载点 (如 / 或 /home)" size="small" style="width:180px" />
              <el-button size="small" type="warning" @click="doDefrag" :disabled="!btrfsMount">碎片整理</el-button>
              <el-button size="small" plain @click="doDeviceStats" :loading="btrfsStatsLoading" :disabled="!btrfsMount">设备统计</el-button>
            </div>
            <div v-if="btrfsMounts.length" class="mt-2 flex gap-1 flex-wrap">
              <el-button v-for="m in btrfsMounts" :key="m" size="small" text @click="btrfsMount = m" style="font-size:11px; padding: 0 6px">{{ m }}</el-button>
            </div>
            <div v-if="btrfsDeviceStatsResult?.devices?.length" class="mt-3 p-2 rounded" style="background:var(--bg-0)">
              <div v-for="d in btrfsDeviceStatsResult.devices" :key="d.device" class="text-xs font-mono" style="padding: 2px 0">{{ d.device }}: {{ d.stats }}</div>
            </div>
            <div v-else-if="!btrfsStatsLoading && btrfsDeviceStatsResult" class="mt-2 text-xs" style="color: var(--text-2)">无设备统计信息</div>
          </template>
        </el-card>
      </div>
      <div class="col-span-12 md:col-span-6">
        <el-card shadow="never">
          <template #header>
            <span class="flex items-center gap-3 font-semibold"><el-icon><Warning /></el-icon>文件系统工具</span>
          </template>
          <!-- fsck -->
          <div class="mb-3">
            <div class="font-semibold text-sm mb-1">文件系统检查</div>
            <div class="flex gap-3 items-center flex-wrap">
              <el-input v-model="fsckDevice" placeholder="/dev/sda1" size="small" style="width:140px" />
              <el-select v-model="fsckType" size="small" style="width:100px" clearable placeholder="自动">
                <el-option label="ext4" value="ext4" /><el-option label="xfs" value="xfs" />
                <el-option label="btrfs" value="btrfs" /><el-option label="auto" value="auto" />
              </el-select>
              <el-checkbox v-model="fsckFix" size="small">修复</el-checkbox>
              <el-button size="small" @click="doFsck">检查</el-button>
            </div>
          </div>
          <!-- resize -->
          <div class="mb-3">
            <div class="font-semibold text-sm mb-1">在线扩容</div>
            <div class="flex gap-3 items-center flex-wrap">
              <el-input v-model="resizeMount" placeholder="挂载点 / 或 /home" size="small" style="width:160px" />
              <el-button size="small" @click="doResize">扩容</el-button>
            </div>
          </div>
          <!-- SMART -->
          <div>
            <div class="font-semibold text-sm mb-1">SMART 健康</div>
            <div class="flex gap-3 items-center">
              <el-input v-model="smartDevice" placeholder="/dev/sda" size="small" style="width:140px" />
              <el-button size="small" @click="doSmart">检测</el-button>
            </div>
            <div v-if="smartResult" class="mt-2 p-2 rounded text-sm" style="background:var(--bg-0)">
              <div>健康: <span :style="{color: smartResult.health==='PASSED'?'var(--green)':'var(--red)'}">{{ smartResult.health }}</span></div>
              <div v-if="smartResult.attributes?.length" class="text-xs mt-1" style="color:var(--text-2)">
                已读取 {{smartResult.attributes.length}} 项 SMART 属性
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- ═══════════ ZFS ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Coin /></el-icon>ZFS</span>
          <el-button size="small" plain @click="loadZfs">刷新</el-button>
        </div>
      </template>
      <div v-if="zfs.installed === false" class="text-sm" style="color: var(--text-2)">ZFS 未安装</div>
      <el-table v-else-if="zfs.pools?.length" :data="zfs.pools" size="small" stripe border>
        <el-table-column prop="name" label="池名称" width="120" />
        <el-table-column prop="size" label="大小" width="80" />
        <el-table-column prop="alloc" label="已分配" width="80" />
        <el-table-column prop="free" label="可用" width="80" />
        <el-table-column prop="health" label="健康" width="80">
          <template #default="{row}"><span :style="{color: row.health==='ONLINE'?'var(--green)':'var(--red)'}">{{row.health}}</span></template>
        </el-table-column>
      </el-table>
      <div v-else class="text-sm" style="color: var(--text-2)">无 ZFS 池</div>
    </el-card>

    <!-- ═══════════ 高级存储 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header><span class="flex items-center gap-3 font-semibold"><el-icon><Setting /></el-icon>高级存储</span></template>
      <el-tabs v-model="advStoreTab">
        <!-- LVM 高级 -->
        <el-tab-pane name="lvm-adv">
          <template #label><span class="text-sm">LVM 高级</span></template>
          <div class="grid grid-cols-12 gap-4">
            <div class="col-span-12 md:col-span-6"><div class="p-4 rounded-lg" style="background:var(--bg-0)"><div class="font-semibold text-sm mb-2">Thin Pool</div><div class="flex gap-3 items-center"><el-input v-model="thinPool.name" placeholder="名称" size="small" style="width:100px" /><el-select v-model="thinPool.vg" size="small" class="w-28" placeholder="VG"><el-option v-for="v in lvm.vgs" :key="v.name" :label="v.name" :value="v.name" /></el-select><el-input v-model="thinPool.size" placeholder="10G" size="small" style="width:80px" /><el-button size="small" @click="doCreateThinPool">创建</el-button></div></div></div>
            <div class="col-span-12 md:col-span-6"><div class="p-4 rounded-lg" style="background:var(--bg-0)"><div class="font-semibold text-sm mb-2">LV 快照</div><div class="flex gap-3 items-center"><el-input v-model="snapForm.lv" placeholder="vg/lv" size="small" style="width:120px" /><el-input v-model="snapForm.name" placeholder="快照名" size="small" style="width:100px" /><el-button size="small" @click="doCreateSnapshot">创建</el-button></div></div></div>
          </div>
        </el-tab-pane>

        <!-- LUKS -->
        <el-tab-pane name="luks">
          <template #label><span class="text-sm">LUKS</span></template>
          <div v-if="luks.installed===false" class="text-sm" style="color:var(--text-2)">cryptsetup 未安装</div>
          <template v-else>
            <div v-if="luks.devices?.length" class="mb-3">
              <div v-for="d in luks.devices" :key="d.name" class="flex items-center justify-between mb-1 text-sm"><span class="font-mono">{{d.name}}</span><span style="color:var(--text-2)">{{d.size}}</span></div>
            </div>
            <div class="flex gap-3 items-center"><el-input v-model="luksDevice" placeholder="/dev/sdb1" size="small" style="width:130px" /><el-input v-model="luksName" placeholder="映射名" size="small" style="width:100px" /><el-input v-model="luksPass" placeholder="密码(可选)" size="small" type="password" show-password style="width:120px" /><el-button size="small" @click="doLuksOpen">打开</el-button><el-button size="small" type="danger" @click="doLuksClose" :disabled="!luksName">关闭</el-button><el-button size="small" plain @click="loadLuks">刷新</el-button></div>
          </template>
        </el-tab-pane>

        <!-- 性能测试 -->
        <el-tab-pane name="bench">
          <template #label><span class="text-sm">性能</span></template>
          <div class="flex gap-3 items-center flex-wrap">
            <el-input v-model="benchDevice" placeholder="/dev/sda" size="small" style="width:130px" />
            <el-select v-model="benchType" size="small" class="w-44">
              <el-option label="hdparm 读速" value="read" /><el-option label="dd 写速" value="write" />
              <el-option label="fio 随机读" value="fio-randread" /><el-option label="fio 随机写" value="fio-randwrite" />
            </el-select>
            <el-button size="small" type="primary" @click="doBenchmark">测试</el-button>
          </div>
          <div v-if="benchResult" class="terminal mt-3" style="min-height:60px;max-height:200px">{{benchResult}}</div>
          <el-divider />
          <el-button size="small" plain @click="loadBenchHistory">历史记录</el-button>
          <div v-if="benchHistory.length" class="mt-2 text-xs" style="max-height:150px;overflow-y:auto">
            <div v-for="(h,i) in benchHistory.slice(0,20)" :key="i" class="py-1 flex gap-2" style="border-bottom:1px solid var(--border)">
              <span style="color:var(--text-2)">{{ h.date }}</span>
              <span class="font-mono">{{ h.device }}</span>
              <span style="color:var(--accent)">{{ h.test_type }}</span>
            </div>
          </div>
        </el-tab-pane>

        <!-- IO 监控 -->
        <el-tab-pane name="io-mon">
          <template #label><span class="text-sm">IO 监控</span></template>
          <el-button size="small" plain class="mb-3" @click="loadIoStats">刷新</el-button>
          <el-table v-if="ioStats.devices?.length" :data="ioStats.devices" size="small" stripe border max-height="300">
            <el-table-column prop="name" label="设备" width="80" />
            <el-table-column label="读/秒" width="90"><template #default="{row}">{{ row.reads }}</template></el-table-column>
            <el-table-column label="写/秒" width="90"><template #default="{row}">{{ row.writes }}</template></el-table-column>
            <el-table-column label="IO使用" width="70"><template #default="{row}">{{ row.ios_in_progress }}</template></el-table-column>
            <el-table-column label="IO等待" width="80"><template #default="{row}">{{ (row.io_ms/1000).toFixed(1) }}s</template></el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- SMART 摘要 -->
        <el-tab-pane name="smart-all">
          <template #label><span class="text-sm">SMART</span></template>
          <el-button size="small" plain class="mb-3" @click="loadSmartAll">刷新</el-button>
          <el-table v-if="smartAll.length" :data="smartAll" size="small" stripe border>
            <el-table-column prop="device" label="设备" width="140"><template #default="{row}"><span class="font-mono text-sm">{{row.device}}</span></template></el-table-column>
            <el-table-column label="健康" width="100"><template #default="{row}"><el-tag :type="row.health==='PASSED'?'success':'danger'" size="small">{{row.health}}</el-tag></template></el-table-column>
            <el-table-column prop="temperature" label="温度" width="70"><template #default="{row}"><span :style="{color: row.temperature>50?'var(--red)':row.temperature>40?'var(--yellow)':'var(--text-1)'}">{{row.temperature}}°C</span></template></el-table-column>
            <el-table-column label="通电时间" width="110"><template #default="{row}">{{ row.power_on_hours ? Math.floor(row.power_on_hours/24)+'天 '+row.power_on_hours%24+'h' : '-' }}</template></el-table-column>
            <el-table-column label="重分配扇区" width="100"><template #default="{row}"><span :style="{color: row.reallocated_sectors>0?'var(--red)':'var(--text-1)'}">{{ row.reallocated_sectors ?? '-' }}</span></template></el-table-column>
            <el-table-column label="自检" width="140">
              <template #default="{row}">
                <el-button size="small" text @click="doSmartTest(row.device, 'short')">短检</el-button>
                <el-button size="small" text type="warning" @click="doSmartTest(row.device, 'long')">长检</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="smartTestMsg" class="mt-2 text-xs" :style="{color: smartTestOk ? 'var(--green)' : 'var(--red)'}">{{ smartTestMsg }}</div>
        </el-tab-pane>

        <!-- ZFS 数据集 -->
        <el-tab-pane name="zfs-ds">
          <template #label><span class="text-sm">ZFS 数据集</span></template>
          <div v-if="zfsDs.length" class="mb-3">
            <el-table :data="zfsDs" size="small" stripe border max-height="250">
              <el-table-column prop="name" label="名称" min-width="180"><template #default="{row}"><span class="font-mono text-sm">{{row.name}}</span></template></el-table-column>
              <el-table-column prop="used" label="已用" width="70" /><el-table-column prop="avail" label="可用" width="70" />
              <el-table-column prop="mountpoint" label="挂载点" width="120" />
              <el-table-column label="操作" width="80"><template #default="{row}"><el-button size="small" type="danger" plain @click="doDestroyZfsDs(row.name)">销毁</el-button></template></el-table-column>
            </el-table>
          </div>
          <div class="flex gap-3 items-center"><el-input v-model="zfsDsName" placeholder="pool/dataset" size="small" style="width:160px" /><el-button size="small" @click="doCreateZfsDs">创建数据集</el-button><el-button size="small" plain @click="loadZfsDs">刷新</el-button></div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Format Dialog -->
    <el-dialog v-model="showFormatDialog" title="格式化分区" width="420px">
      <el-alert type="error" :closable="false" class="mb-4">
        <template #title>
          危险操作！格式化将清除 {{ formatTarget?.name }} 上的所有数据，不可恢复！
        </template>
      </el-alert>
      <el-form label-width="80px" size="small">
        <el-form-item label="文件系统">
          <el-select v-model="formatFs" class="w-full">
            <el-option label="ext4" value="ext4" />
            <el-option label="xfs" value="xfs" />
            <el-option label="btrfs" value="btrfs" />
            <el-option label="ntfs" value="ntfs" />
            <el-option label="vfat (FAT32)" value="vfat" />
            <el-option label="exfat" value="exfat" />
          </el-select>
        </el-form-item>
        <el-form-item label="卷标">
          <el-input v-model="formatLabel" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFormatDialog = false" :disabled="formatRunning">取消</el-button>
        <el-button type="danger" @click="doFormat" :loading="formatRunning">确定格式化</el-button>
      </template>
    </el-dialog>

    <!-- LV Resize Dialog -->
    <el-dialog v-model="lvResizeVisible" title="扩容 LV" width="400px">
      <p class="mb-3">扩容 {{ lvResizeTarget?.name }} ({{ lvResizeTarget?.vg }})</p>
      <el-input v-model="lvResizeSize" placeholder="增加大小 (如 5G)" size="small" />
      <template #footer>
        <el-button @click="lvResizeVisible=false">取消</el-button>
        <el-button type="primary" @click="doResizeLv">确定</el-button>
      </template>
    </el-dialog>

    <!-- RAID Detail Dialog -->
    <el-dialog v-model="raidDetailVisible" title="RAID 详情" width="600px">
      <pre class="text-xs font-mono whitespace-pre-wrap" style="background: var(--bg-1); padding: 12px; border-radius: 6px; max-height: 400px; overflow: auto">{{ raidDetailContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { systemApi } from '@/api/system'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { Refresh, Top, Bottom, Histogram, EditPen, FolderChecked, Warning, Coin, FolderOpened, Setting } from '@element-plus/icons-vue'
import { diskApi } from '@/api/disk'
import { storageApi } from '@/api/storage'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import type { BlockDevice, DiskUsageDevice, LvmStatus, BtrfsStatus, ZfsStatus, LuksStatus } from '@/types/api'

const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['lvm','btrfs','zfs','smartctl','cryptsetup','mdadm'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }
const { confirm: showConfirm } = useConfirm()
const devices = ref<BlockDevice[]>([])
const devicesLoading = ref(true)
const usage = ref('')
const usageDevices = ref<DiskUsageDevice[]>([])
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

const deviceSortKey = ref('')
const deviceSortOrder = ref<'ascending' | 'descending' | null>(null)

const sortedDevices = computed<FlatDevice[]>(() => {
  const arr = [...flatDevices.value]
  if (deviceSortKey.value && deviceSortOrder.value) {
    arr.sort((a, b) => {
      const va = (a as any)[deviceSortKey.value] ?? ''
      const vb = (b as any)[deviceSortKey.value] ?? ''
      if (va < vb) return deviceSortOrder.value === 'ascending' ? -1 : 1
      if (va > vb) return deviceSortOrder.value === 'ascending' ? 1 : -1
      return 0
    })
  }
  return arr
})

function onDeviceSort({ prop, order }: { prop: string; order: string }) {
  deviceSortKey.value = prop
  deviceSortOrder.value = order as 'ascending' | 'descending' | null
}

function parsePercent(pct: string): number {
  const n = parseInt(pct)
  return isNaN(n) ? 0 : n
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const v = bytes / Math.pow(k, i)
  return v.toFixed(i === 0 ? 0 : 1) + ' ' + sizes[i]
}

function lvTypeLabel(attr: string): string {
  if (!attr || attr.length < 1) return 'linear'
  const t = attr[0]
  const map: Record<string, string> = {
    'C': 'cache', 'm': 'mirror', 'M': 'mirror (no sync)',
    'r': 'raid', 'R': 'raid (no sync)', 's': 'snapshot',
    'S': 'snapshot (inv)', 't': 'thin', 'T': 'thin-pool',
    'v': 'virtual', 'V': 'thin volume',
    'l': 'linear', '-': 'linear',
  }
  return map[t] || 'linear'
}

async function load() {
  devicesLoading.value = true
  try {
    const [devs, u, f, us] = await Promise.all([
      diskApi.getDevices(),
      diskApi.getUsage(),
      diskApi.getFstab(),
      diskApi.getUsageStructured(),
    ])
    devices.value = devs; usage.value = u.usage; fstab.value = f.content
    usageDevices.value = us.devices
  } catch { toast.error('加载失败') } finally {
    devicesLoading.value = false
  }
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
const raidCollapse = ref<string[]>(['raid'])
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
  } catch { toast.error('加载 RAID 信息失败') }
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

// ── LVM ──
const lvm = ref<LvmStatus>({ installed: false, pvs: [], vgs: [], lvs: [] })
const lvForm = ref({ name: '', vg: '', size: '' })
const lvResizeVisible = ref(false)
const lvResizeTarget = ref<any>(null)
const lvResizeSize = ref('')
async function loadLvm() {
  try { lvm.value = await storageApi.getLvmStatus() } catch {}
}
async function doCreateLv() {
  if (!lvForm.value.name || !lvForm.value.vg || !lvForm.value.size) return toast.warning('请填写完整')
  try {
    const r = await storageApi.createLv(lvForm.value.name, lvForm.value.vg, lvForm.value.size)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) { lvForm.value = { name: '', vg: '', size: '' }; await loadLvm() }
  } catch { toast.error('创建失败') }
}
function showLvResize(row: any) { lvResizeTarget.value = row; lvResizeSize.value = ''; lvResizeVisible.value = true }
async function doResizeLv() {
  if (!lvResizeSize.value) return toast.warning('请输入大小')
  try {
    const r = await storageApi.resizeLv(`${lvResizeTarget.value.vg}/${lvResizeTarget.value.name}`, lvResizeSize.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) { lvResizeVisible.value = false; await loadLvm() }
  } catch { toast.error('扩容失败') }
}
async function doRemoveLv(row: any) {
  if (!(await showConfirm('删除 LV', `确定删除 ${row.vg}/${row.name}？此操作不可逆！`, true))) return
  try {
    const r = await storageApi.removeLv(`${row.vg}/${row.name}`)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) await loadLvm()
  } catch { toast.error('删除失败') }
}

// ── Btrfs ──
const btrfs = ref<BtrfsStatus>({ installed: false, filesystems: [], subvolumes: [] })
const btrfsSubvol = ref('')
const btrfsMount = ref('/')
const btrfsMounts = computed(() => {
  const mounts: string[] = []
  for (const d of usageDevices.value) {
    const t = (d as any).fstype || (d as any).type || ''
    if (t === 'btrfs' && d.target && !mounts.includes(d.target)) {
      mounts.push(d.target)
    }
  }
  // Also check /proc/mounts
  if (!mounts.length) {
    for (const fs of btrfs.value.filesystems || []) {
      for (const dev of fs.devices || []) {
        // Try to find mount point via findmnt in backend
        if (dev.path) mounts.push('/')
        break
      }
    }
  }
  return mounts.length ? mounts : (btrfs.value.installed ? ['/'] : [])
})
const btrfsDeviceStatsResult = ref<any>(null)
const btrfsStatsLoading = ref(false)
async function loadBtrfs() {
  try { btrfs.value = await storageApi.getBtrfsStatus() } catch {}
}
async function doCreateSubvol() {
  if (!btrfsSubvol.value) return toast.warning('请输入子卷路径')
  try {
    const r = await storageApi.createSubvolume(btrfsSubvol.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) { btrfsSubvol.value = ''; await loadBtrfs() }
  } catch { toast.error('创建失败') }
}
async function doScrub() {
  if (!(await showConfirm('Btrfs Scrub', 'Scrub 可能耗时较长，确定执行？'))) return
  try {
    const r = await storageApi.btrfsScrub('/')
    toast.show(r.message, r.success ? 'success' : 'error')
  } catch { toast.error('Scrub 失败') }
}
async function doDefrag() {
  if (!btrfsMount.value) return toast.warning('请输入挂载点')
  if (!(await showConfirm('Btrfs 碎片整理', `确定对 ${btrfsMount.value} 执行碎片整理？可能耗时较长。`))) return
  try {
    const r = await storageApi.btrfsDefrag(btrfsMount.value)
    toast.show(r.message, r.success ? 'success' : 'error')
  } catch { toast.error('碎片整理失败') }
}
async function doDeviceStats() {
  if (!btrfsMount.value) return toast.warning('请输入挂载点')
  btrfsStatsLoading.value = true
  try { btrfsDeviceStatsResult.value = await storageApi.btrfsDeviceStats(btrfsMount.value) } catch { toast.error('获取设备统计失败') }
  finally { btrfsStatsLoading.value = false }
}

// ── 格式化分区 ──
const showFormatDialog = ref(false)
const formatTarget = ref<FlatDevice | null>(null)
const formatFs = ref('ext4')
const formatLabel = ref('')
const formatRunning = ref(false)

function openFormatDialog(row: FlatDevice) {
  formatTarget.value = row
  formatFs.value = 'ext4'
  formatLabel.value = ''
  formatRunning.value = false
  showFormatDialog.value = true
}

async function doFormat() {
  if (!formatTarget.value) return
  if (!(await showConfirm('格式化分区',
    `确定格式化 /dev/${formatTarget.value.name} 为 ${formatFs.value}？这是不可逆操作！`, true))) return
  formatRunning.value = true
  try {
    const r = await storageApi.formatPartition(
      `/dev/${formatTarget.value.name}`, formatFs.value, formatLabel.value
    )
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) { showFormatDialog.value = false; load() }
  } catch { toast.error('格式化失败') }
  finally { formatRunning.value = false }
}

// ── fsck / Resize / SMART ──
const fsckDevice = ref('')
const fsckType = ref('auto')
const fsckFix = ref(false)
const resizeMount = ref('/')
const smartDevice = ref('')
const smartResult = ref<Record<string,any>|null>(null)
async function doFsck() {
  if (!fsckDevice.value) return toast.warning('请输入设备路径')
  if (!(await showConfirm('fsck', `确定${fsckFix.value?'修复':'检查'} ${fsckDevice.value}？`))) return
  try {
    const r = await storageApi.runFsck(fsckDevice.value, fsckType.value, fsckFix.value)
    toast.show(r.message, r.success ? 'success' : 'error')
  } catch { toast.error('操作失败') }
}
async function doResize() {
  if (!resizeMount.value) return toast.warning('请输入挂载点')
  if (!(await showConfirm('扩容', `确定扩容 ${resizeMount.value}？`))) return
  try {
    const r = await storageApi.resizeFs(resizeMount.value)
    toast.show(r.message, r.success ? 'success' : 'error')
  } catch { toast.error('扩容失败') }
}
async function doSmart() {
  if (!smartDevice.value) return toast.warning('请输入设备路径')
  try {
    smartResult.value = await storageApi.getSmart(smartDevice.value)
  } catch { toast.error('SMART 检测失败') }
}

// ── ZFS ──
const zfs = ref<ZfsStatus>({ installed: false, pools: [] })
async function loadZfs() { try { zfs.value = await storageApi.getZfsStatus() } catch {} }

// ── Advanced storage ──
const advStoreTab = ref('lvm-adv')
const thinPool = ref({ name: '', vg: '', size: '' })
const snapForm = ref({ lv: '', name: '' })
const luks = ref<LuksStatus>({ installed: false, devices: [] }); const luksDevice = ref(''); const luksName = ref(''); const luksPass = ref('')
const benchDevice = ref(''); const benchType = ref('read'); const benchResult = ref('')
const benchHistory = ref<any[]>([])
async function loadBenchHistory() { try { benchHistory.value = (await storageApi.getBenchmarkHistory()).history || [] } catch {} }
const smartAll = ref<any[]>([])
const zfsDs = ref<any[]>([]); const zfsDsName = ref('')
const ioStats = ref<any>({ devices: [] })
async function loadIoStats() { try { ioStats.value = await storageApi.getIoStats() } catch {} }

async function doCreateThinPool() { try { const r = await storageApi.createThinPool(thinPool.value.name, thinPool.value.vg, thinPool.value.size); toast.show(r.message, r.success?'success':'error'); if(r.success){ thinPool.value={name:'',vg:'',size:''}; await loadLvm() } } catch { toast.error('创建失败') } }
async function doCreateSnapshot() { try { const r = await storageApi.createLvSnapshot(snapForm.value.lv, snapForm.value.name); toast.show(r.message, r.success?'success':'error'); if(r.success) snapForm.value={lv:'',name:''} } catch { toast.error('创建失败') } }
async function loadLuks() { try { luks.value = await storageApi.getLuksStatus() } catch {} }
async function doLuksOpen() { try { const r = await storageApi.luksOpen(luksDevice.value, luksName.value, luksPass.value); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadLuks() } catch { toast.error('操作失败') } }
async function doLuksClose() { try { const r = await storageApi.luksClose(luksName.value); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadLuks() } catch { toast.error('操作失败') } }
async function doBenchmark() { benchResult.value = ''; try { const r = await storageApi.runBenchmark(benchDevice.value, benchType.value); benchResult.value = r.message || '' } catch { toast.error('测试失败') } }
// SMART 自检
const smartTestMsg = ref('')
const smartTestOk = ref(false)
async function doSmartTest(device: string, testType: string) {
  try { const r = await storageApi.startSmartTest(device, testType); smartTestMsg.value = r.message; smartTestOk.value = r.success } catch { smartTestMsg.value = '启动失败'; smartTestOk.value = false }
}

async function loadSmartAll() { try { smartAll.value = (await storageApi.getSmartAll()).devices||[] } catch {} }
async function loadZfsDs() { try { zfsDs.value = (await storageApi.getZfsDatasets()).datasets||[] } catch {} }
async function doCreateZfsDs() { try { const r = await storageApi.createZfsDataset(zfsDsName.value); toast.show(r.message, r.success?'success':'error'); if(r.success){ zfsDsName.value=''; await loadZfsDs() } } catch { toast.error('创建失败') } }
async function doDestroyZfsDs(name: string) { if(!(await showConfirm('销毁',`确定销毁 ${name}？不可逆！`,true))) return; try { const r = await storageApi.destroyZfsDataset(name); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadZfsDs() } catch { toast.error('销毁失败') } }

// Auto-refresh
const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(() => { load(); loadLvm(); loadBtrfs(); loadZfs() }, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}
onMounted(() => { load(); loadRaid(); loadLvm(); loadBtrfs(); loadZfs(); loadLuks(); loadSmartAll(); loadZfsDs(); fetchFeatures() })
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>

<style scoped>
.mono { font-family: 'JetBrains Mono', monospace; }
</style>
