<template>
  <div>
    <div class="page-title"><el-icon><Connection /></el-icon>网络设置
      <el-switch v-model="autoRefresh" size="small" @change="toggleAutoRefresh" class="ml-3" active-text="30s" title="自动刷新" />
    </div>

    <FeatureStatus :features="features" />

    <!-- ═══════════ 网络接口（卡片式） ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Link /></el-icon>网络接口</span>
          <el-button size="small" plain @click="load" :loading="loading"><el-icon><Refresh /></el-icon>刷新</el-button>
        </div>
      </template>
      <div v-loading="loading" class="grid grid-cols-12 gap-4">
        <div v-for="iface in interfaces" :key="iface.name"
          class="col-span-12 md:col-span-6 xl:col-span-4">
          <div class="iface-card p-4 rounded-lg" :class="{ down: !iface.is_up }"
            style="background: var(--bg-0); border: 1px solid var(--border)">
            <!-- 名称 + 状态 -->
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="status-dot" :class="iface.is_up ? 'up' : 'down'"></span>
                <span class="font-mono font-semibold text-sm">{{ iface.name }}</span>
              </div>
              <el-tag :type="iface.is_up ? 'success' : 'danger'" size="small">{{ iface.is_up ? 'UP' : 'DOWN' }}</el-tag>
            </div>
            <!-- 地址信息 -->
            <div class="iface-info mb-2">
              <div v-if="iface.ipv4.length" class="info-row">
                <span class="info-label">IPv4</span>
                <span class="font-mono" style="word-break:break-all">{{ iface.ipv4.join(', ') }}</span>
              </div>
              <div v-else class="info-row"><span class="info-label">IPv4</span><span style="color:var(--text-2)">—</span></div>
              <div v-if="iface.ipv6.length" class="info-row">
                <span class="info-label">IPv6</span>
                <span class="font-mono" style="font-size:11px; word-break:break-all; line-height:1.4">{{ iface.ipv6.join(', ') }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">MAC</span>
                <span class="font-mono">{{ iface.mac || '—' }}</span>
                <span v-if="iface.speed" class="info-label ml-3">速率</span>
                <span v-if="iface.speed" style="color:var(--text-1)">{{ iface.speed }}Mbps</span>
              </div>
              <div v-if="iface.mtu" class="info-row">
                <span class="info-label">MTU</span>
                <span style="color:var(--text-1)">{{ iface.mtu }}</span>
              </div>
            </div>
            <!-- 操作按钮 -->
            <div class="flex gap-1 items-center">
              <el-button size="small" type="success" text @click="ifaceAction(iface.name, 'up')" :disabled="iface.is_up">启用</el-button>
              <el-button size="small" type="danger" text @click="ifaceAction(iface.name, 'down')" :disabled="!iface.is_up">禁用</el-button>
              <el-button size="small" type="warning" text @click="ifaceAction(iface.name, 'restart')">重启</el-button>
              <div class="flex-1"></div>
              <el-button size="small" plain text @click="openIpDialog(iface)">配置IP</el-button>
            </div>
          </div>
        </div>
        <div v-if="!interfaces.length" class="col-span-12 text-center py-6" style="color: var(--text-2)">无网络接口数据</div>
      </div>
    </el-card>

    <!-- ═══════════ 防火墙 + 端口监听 ═══════════ -->
    <div class="grid grid-cols-12 gap-5 mb-5">
      <div class="col-span-12 md:col-span-7">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="flex items-center gap-3 font-semibold"><el-icon><Shield /></el-icon>防火墙</span>
              <span class="text-xs" style="color:var(--text-2)">管理: {{ netManager || '...' }}</span>
            </div>
          </template>
          <!-- 防火墙状态标签 -->
          <div class="mb-3">
            <el-tag v-if="fw.active" type="success" size="small">{{ fw.active === 'ufw' ? 'UFW' : fw.active === 'firewalld' ? 'firewalld' : fw.active === 'nftables' ? 'nftables' : fw.active === 'iptables' ? 'iptables' : fw.active }} (active)</el-tag>
            <el-tag v-else type="warning" size="small">无活动防火墙</el-tag>
          </div>
          <div class="flex gap-2 mb-3 flex-wrap">
            <el-tag v-if="fw.ufw?.installed" :type="fw.ufw?.active ? 'success' : 'info'" size="small" @click="fwActiveTool='ufw'; viewRules()" style="cursor:pointer">UFW {{ fw.ufw?.active ? '●' : '○' }}</el-tag>
            <el-tag v-if="fw.firewalld?.installed" :type="fw.firewalld?.active ? 'success' : 'info'" size="small" @click="fwActiveTool='firewalld'; viewRules()" style="cursor:pointer">firewalld {{ fw.firewalld?.active ? '●' : '○' }}</el-tag>
            <el-tag v-if="fw.nftables?.installed" :type="fw.nftables?.active ? 'success' : 'info'" size="small" @click="fwActiveTool='nftables'; viewRules()" style="cursor:pointer">nftables {{ fw.nftables?.active ? '●' : '○' }}</el-tag>
            <el-tag v-if="fw.iptables?.installed" :type="fw.iptables?.active ? 'success' : 'info'" size="small" @click="fwActiveTool='iptables'; viewRules()" style="cursor:pointer">iptables</el-tag>
            <el-tag v-if="!fw.installed?.length" type="warning" size="small">未检测到防火墙</el-tag>
          </div>
          <!-- UFW / firewalld 专用操作 -->
          <div v-if="fw.ufw?.active || fw.firewalld?.active" class="flex gap-2 mb-3 flex-wrap">
            <el-button size="small" type="primary" plain @click="showAllowPort = true"><el-icon class="mr-1"><CirclePlus /></el-icon>允许</el-button>
            <el-button size="small" type="danger" plain @click="showDenyPort = true"><el-icon class="mr-1"><Remove /></el-icon>禁止</el-button>
          </div>
          <!-- 高级命令 -->
          <div class="flex gap-3 items-center">
            <el-input v-model="fwCmd" placeholder="自定义命令..." size="small" class="flex-1" @keyup.enter="runFwCmd" />
            <el-button size="small" plain @click="runFwCmd">执行</el-button>
          </div>
          <div v-if="fwOutput" class="terminal mt-3" style="min-height:60px; max-height:180px">{{ fwOutput }}</div>
          <!-- Firewalld 区域 -->
          <div v-if="fwZones.zones?.length" class="mt-4">
            <el-divider content-position="left" class="!my-2">区域</el-divider>
            <div class="flex flex-wrap gap-1">
              <el-tag v-for="z in fwZones.zones" :key="z.name" size="small" :type="z.is_default?'success':z.masquerade?'warning':'info'"
                @click="loadFwRules(z.name)" style="cursor:pointer">
                {{ z.name }}{{ z.is_default ? ' (默认)' : '' }}
              </el-tag>
            </div>
            <div v-if="fwRichRules.length" class="mt-2 terminal text-xs" style="min-height:40px;max-height:120px">
              <div v-for="(r,i) in fwRichRules" :key="i">{{ r.raw }}</div>
            </div>
          </div>
        </el-card>
      </div>
      <div class="col-span-12 md:col-span-5">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="flex items-center gap-3 font-semibold"><el-icon><Monitor /></el-icon>端口监听</span>
              <el-button size="small" plain :loading="portsLoading" @click="loadPorts"><el-icon><Refresh /></el-icon></el-button>
            </div>
          </template>
          <el-table :data="ports" size="small" stripe border max-height="280px" v-if="ports.length">
            <el-table-column prop="protocol" label="协议" width="55" />
            <el-table-column prop="local_address" label="地址" min-width="140">
              <template #default="{row}"><span class="font-mono text-sm">{{row.local_address}}</span></template>
            </el-table-column>
            <el-table-column prop="process" label="进程" min-width="100">
              <template #default="{row}"><span class="text-xs">{{row.process || '—'}}</span></template>
            </el-table-column>
          </el-table>
          <div v-else class="text-sm text-center py-4" style="color: var(--text-2)">点击刷新加载</div>
        </el-card>
      </div>
    </div>

    <!-- ═══════════ DNS ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Share /></el-icon>DNS</span>
      </template>
      <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12 md:col-span-6">
          <div class="font-semibold text-sm mb-2">当前 DNS</div>
          <div class="mono p-3 text-sm rounded-lg" style="background: var(--bg-0); min-height: 40px">
            <template v-if="dns.length">
              <span v-for="d in dns" :key="d" class="mr-4" style="color: var(--accent)">{{ d }}</span>
            </template>
            <span v-else style="color: var(--text-2)">未配置</span>
          </div>
        </div>
        <div class="col-span-12 md:col-span-6">
          <div class="font-semibold text-sm mb-2">修改</div>
          <div class="flex gap-3 items-center mb-2">
            <el-input v-model="dnsPrimary" placeholder="主 DNS" size="small" style="width:160px" />
            <el-input v-model="dnsBackup" placeholder="备 DNS" size="small" style="width:160px" />
          </div>
          <el-button size="small" type="primary" :loading="dnsSaving" @click="saveDns">保存</el-button>
        </div>
      </div>
    </el-card>

    <!-- ═══════════ 网络绑定 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-3 font-semibold"><el-icon><Connection /></el-icon>网络绑定 (Bond)</span>
          <el-button size="small" plain @click="loadBonds">刷新</el-button>
        </div>
      </template>
      <!-- 已有 Bond -->
      <el-table v-if="bondData.bonds?.length" :data="bondData.bonds" size="small" stripe border class="mb-4">
        <el-table-column prop="name" label="名称" width="80" />
        <el-table-column label="从接口" min-width="150">
          <template #default="{row}"><span class="font-mono text-sm">{{row.slaves?.join(', ')}}</span></template>
        </el-table-column>
        <el-table-column prop="mode" label="模式" width="100" />
        <el-table-column prop="status" label="状态" width="70">
          <template #default="{row}"><el-tag :type="row.status==='UP'?'success':'info'" size="small">{{row.status}}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="70">
          <template #default="{row}"><el-button size="small" type="danger" plain @click="doDeleteBond(row.name)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <!-- 创建 Bond -->
      <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12 md:col-span-3">
          <label class="block text-xs mb-1" style="color:var(--text-2)">名称</label>
          <el-input v-model="bondName" placeholder="bond0" size="small" />
        </div>
        <div class="col-span-12 md:col-span-4">
          <label class="block text-xs mb-1" style="color:var(--text-2)">模式</label>
          <el-select v-model="bondMode" size="small" class="w-full">
            <el-option v-for="(desc, mode) in bondData.modes" :key="mode" :label="`${mode} — ${desc}`" :value="mode" />
          </el-select>
        </div>
        <div class="col-span-12 md:col-span-5">
          <label class="block text-xs mb-1" style="color:var(--text-2)">从接口（至少 2 个）</label>
          <el-select v-model="bondSlaves" multiple filterable size="small" class="w-full" placeholder="选择接口">
            <el-option v-for="s in bondData.slaves" :key="s" :label="s" :value="s" />
          </el-select>
        </div>
      </div>
      <el-button size="small" type="primary" class="mt-4" @click="doCreateBond" :disabled="bondSlaves.length < 2">创建 Bond</el-button>
    </el-card>

    <!-- ═══════════ 高级网络 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Setting /></el-icon>高级网络</span>
      </template>
      <el-tabs v-model="advTab">
        <!-- VLAN -->
        <el-tab-pane name="vlan">
          <template #label><span class="text-sm">VLAN</span></template>
          <div v-if="vlanData.length" class="mb-3">
            <el-table :data="vlanData" size="small" stripe border>
              <el-table-column prop="name" label="接口" width="120"><template #default="{row}"><span class="font-mono text-sm">{{row.name}}</span></template></el-table-column>
              <el-table-column prop="id" label="VLAN ID" width="80" />
              <el-table-column prop="parent" label="父接口" width="100" />
              <el-table-column label="操作" width="80">
                <template #default="{row}"><el-button size="small" type="danger" plain @click="doDeleteVlan(row.name)">删除</el-button></template>
              </el-table-column>
            </el-table>
          </div>
          <div class="flex gap-3 items-center flex-wrap">
            <el-select v-model="vlanParent" size="small" class="w-32" placeholder="父接口"><el-option v-for="i in interfaces" :key="i.name" :label="i.name" :value="i.name" /></el-select>
            <el-input v-model="vlanId" placeholder="ID" size="small" style="width:70px" />
            <el-button size="small" @click="doCreateVlan" :disabled="!vlanParent||!vlanId">创建 VLAN</el-button>
            <el-button size="small" plain @click="loadVlans">刷新</el-button>
          </div>
        </el-tab-pane>

        <!-- Bridge -->
        <el-tab-pane name="bridge">
          <template #label><span class="text-sm">Bridge</span></template>
          <div v-if="bridgeData.length" class="mb-3">
            <div v-for="br in bridgeData" :key="br.name" class="p-3 mb-2 rounded-lg" style="background:var(--bg-0);border:1px solid var(--border)">
              <div class="flex items-center justify-between mb-1">
                <span class="font-mono font-semibold text-sm">{{ br.name }}</span>
                <el-tag :type="br.up?'success':'info'" size="small">{{ br.up?'UP':'DOWN' }}</el-tag>
              </div>
              <div class="text-xs mb-2" style="color:var(--text-2)">
                成员: <span class="font-mono">{{ br.members?.join(', ') || '(空)' }}</span>
              </div>
              <div class="flex gap-1">
                <el-select v-model="brAddMember[br.name]" size="small" class="w-24" placeholder="加成员"><el-option v-for="i in interfaces" :key="i.name" :label="i.name" :value="i.name" /></el-select>
                <el-button size="small" plain @click="doBridgeAdd(br.name)" :disabled="!brAddMember[br.name]">加入</el-button>
                <el-button size="small" type="danger" plain @click="doDeleteBridge(br.name)">删除桥</el-button>
              </div>
            </div>
          </div>
          <div class="flex gap-3 items-center">
            <el-input v-model="bridgeName" placeholder="br0" size="small" style="width:100px" />
            <el-button size="small" @click="doCreateBridge">创建 Bridge</el-button>
            <el-button size="small" plain @click="loadBridges">刷新</el-button>
          </div>
        </el-tab-pane>

        <!-- Routes -->
        <el-tab-pane name="routes">
          <template #label><span class="text-sm">路由表</span></template>
          <el-table :data="routeData" size="small" stripe border max-height="300">
            <el-table-column prop="dst" label="目标" min-width="160"><template #default="{row}"><span class="font-mono text-sm">{{row.dst}}</span></template></el-table-column>
            <el-table-column prop="gateway" label="网关" width="130"><template #default="{row}"><span class="font-mono text-sm">{{row.gateway||'—'}}</span></template></el-table-column>
            <el-table-column prop="dev" label="接口" width="80" />
            <el-table-column prop="metric" label="Metric" width="60" />
            <el-table-column label="操作" width="70">
              <template #default="{row}"><el-button size="small" type="danger" plain @click="doDeleteRoute(row)">删除</el-button></template>
            </el-table-column>
          </el-table>
          <div class="flex gap-3 items-center mt-3 flex-wrap">
            <el-input v-model="routeDst" placeholder="目标 (0.0.0.0/0)" size="small" style="width:160px" />
            <el-input v-model="routeGw" placeholder="网关" size="small" style="width:130px" />
            <el-input v-model="routeDev" placeholder="接口" size="small" style="width:90px" />
            <el-button size="small" @click="doAddRoute">添加</el-button>
            <el-button size="small" plain @click="loadRoutes">刷新</el-button>
          </div>
        </el-tab-pane>

        <!-- WireGuard -->
        <el-tab-pane name="wireguard">
          <template #label><span class="text-sm">WireGuard</span></template>
          <el-alert v-if="!wgAvailable" type="warning" :closable="false" class="mb-3" title="WireGuard 不可用 (wireguard-tools 或内核模块缺失)" />
          <div v-if="wgData.length" class="mb-3">
            <div v-for="wg in wgData" :key="wg.name" class="p-3 mb-2 rounded-lg flex items-center justify-between" style="background:var(--bg-0);border:1px solid var(--border)">
              <div>
                <span class="font-mono font-semibold text-sm">{{ wg.name }}</span>
                <span class="text-xs ml-2" style="color:var(--text-2)">port {{ wg.port||'—' }} · peers {{ wg.peers?.length||0 }}</span>
              </div>
              <el-button size="small" type="danger" plain @click="doDeleteWg(wg.name)">删除</el-button>
            </div>
          </div>
          <div class="flex gap-3 items-center">
            <el-input v-model="wgName" placeholder="wg0" size="small" style="width:100px" />
            <el-button size="small" @click="doCreateWg" :disabled="!wgAvailable">创建</el-button>
            <el-button size="small" plain @click="loadWireguard">刷新</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- ═══════════ 网络诊断 ═══════════ -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <span class="flex items-center gap-3 font-semibold"><el-icon><Search /></el-icon>网络诊断</span>
      </template>
      <div class="flex gap-4 mb-4 items-center">
        <el-input v-model="diagHost" placeholder="主机名或 IP" size="small" class="w-56" @keyup.enter="doPing" />
        <el-button size="small" @click="doPing" :loading="diagLoading==='ping'">Ping</el-button>
        <el-button size="small" @click="doTraceroute" :loading="diagLoading==='trace'">Traceroute</el-button>
        <el-button size="small" @click="doDnsLookup" :loading="diagLoading==='dns'">DNS</el-button>
        <el-button size="small" @click="doPortScan" :loading="diagLoading==='scan'">端口</el-button>
        <el-button size="small" plain @click="doConnectivity" :loading="diagLoading==='conn'">连通性</el-button>
      </div>
      <!-- Ping Stats -->
      <div v-if="diagResult?.stats" class="grid grid-cols-6 gap-2 mb-2 text-xs">
        <div class="p-2 rounded text-center" style="background:var(--bg-0)"><div style="color:var(--text-2)">发送</div><div class="font-mono font-semibold">{{ diagResult.stats.transmitted }}</div></div>
        <div class="p-2 rounded text-center" style="background:var(--bg-0)"><div style="color:var(--text-2)">接收</div><div class="font-mono font-semibold" :style="{color: diagResult.stats.received>0?'var(--green)':'var(--red)'}">{{ diagResult.stats.received }}</div></div>
        <div class="p-2 rounded text-center" style="background:var(--bg-0)"><div style="color:var(--text-2)">丢包</div><div class="font-mono font-semibold">{{ diagResult.stats.loss }}</div></div>
        <div class="p-2 rounded text-center" style="background:var(--bg-0)"><div style="color:var(--text-2)">最小</div><div class="font-mono font-semibold">{{ diagResult.stats.min || '—' }}</div></div>
        <div class="p-2 rounded text-center" style="background:var(--bg-0)"><div style="color:var(--text-2)">平均</div><div class="font-mono font-semibold">{{ diagResult.stats.avg || '—' }}</div></div>
        <div class="p-2 rounded text-center" style="background:var(--bg-0)"><div style="color:var(--text-2)">最大</div><div class="font-mono font-semibold">{{ diagResult.stats.max || '—' }}</div></div>
      </div>
      <!-- DNS Records -->
      <div v-if="diagResult?.records" class="text-xs font-mono" style="max-height:150px;overflow-y:auto">
        <div v-for="(r,i) in diagResult.records" :key="i" class="py-0.5">{{ r }}</div>
      </div>
      <!-- Port Scan -->
      <div v-if="diagResult?.results" class="flex flex-wrap gap-1">
        <el-tag v-for="(r,i) in diagResult.results" :key="i" size="small" :type="r.open?'success':'info'">
          {{ r.port }} ({{ r.service }}) {{ r.open ? '●' : '○' }}
        </el-tag>
      </div>
      <!-- Connectivity -->
      <div v-if="diagResult?.ipv4 !== undefined" class="flex flex-wrap gap-2 text-xs">
        <el-tag :type="diagResult.ipv4?'success':'danger'" size="small">IPv4{{ diagResult.ipv4?' ✓':' ✗' }}</el-tag>
        <el-tag :type="diagResult.ipv6?'success':'info'" size="small">IPv6{{ diagResult.ipv6?' ✓':' ✗' }}</el-tag>
        <el-tag :type="diagResult.dns?'success':'danger'" size="small">DNS{{ diagResult.dns?' ✓':' ✗' }}</el-tag>
        <el-tag :type="diagResult.gateway?'success':'danger'" size="small">网关{{ diagResult.gateway?' ✓':' ✗' }}</el-tag>
        <el-tag :type="diagResult.internet?'success':'danger'" size="small">互联网{{ diagResult.internet?' ✓':' ✗' }}</el-tag>
      </div>
      <!-- Raw Output -->
      <div v-if="diagResult?.output" class="terminal mt-2 text-xs" style="min-height:60px;max-height:200px;white-space:pre-wrap;word-break:break-all">{{ diagResult.output }}</div>
      <div v-if="diagResult?.error" class="text-xs mt-2" style="color:var(--red)">{{ diagResult.error }}</div>
    </el-card>

    <!-- ═══════════ 弹窗 ═══════════ -->
    <el-dialog v-model="showIpDialog" title="配置 IP" width="420px">
      <!-- 当前状态 -->
      <el-alert v-if="ipMode !== 'dhcp'" type="info" :closable="false" class="mb-4">
        <template #title>
          <div class="text-sm">
            <span class="font-mono font-semibold">{{ ipIface }}</span>
            <span v-if="ipAddr"> 当前: {{ ipAddr }}/{{ ipMask }}</span>
            <span v-else> 无静态 IP 配置</span>
          </div>
        </template>
      </el-alert>
      <el-alert v-else type="warning" :closable="false" class="mb-4">
        <template #title>
          <span class="font-mono font-semibold">{{ ipIface }}</span> 当前使用 DHCP 动态获取 IP
        </template>
      </el-alert>
      <el-form label-width="80px" size="small">
        <el-form-item label="模式">
          <el-radio-group v-model="ipMode">
            <el-radio value="dhcp">DHCP</el-radio>
            <el-radio value="static">静态</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="ipMode === 'static'">
          <el-form-item label="IP"><el-input v-model="ipAddr" /></el-form-item>
          <el-form-item label="掩码"><el-input v-model="ipMask" style="width:80px" /></el-form-item>
          <el-form-item label="网关"><el-input v-model="ipGw" /></el-form-item>
          <el-form-item label="DNS"><el-input v-model="ipDns" /></el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showIpDialog = false">取消</el-button>
        <el-button type="primary" @click="applyIpConfig">应用</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAllowPort" title="允许端口" width="380px">
      <el-form label-width="70px">
        <el-form-item label="端口"><el-input v-model="portForm.port" placeholder="8080" /></el-form-item>
        <el-form-item label="协议">
          <el-select v-model="portForm.protocol" class="w-full">
            <el-option label="TCP" value="tcp" /><el-option label="UDP" value="udp" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAllowPort = false">取消</el-button>
        <el-button type="primary" @click="allowPort">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDenyPort" title="禁止端口" width="380px">
      <el-form label-width="70px">
        <el-form-item label="端口"><el-input v-model="portForm.port" placeholder="8080" /></el-form-item>
        <el-form-item label="协议">
          <el-select v-model="portForm.protocol" class="w-full">
            <el-option label="TCP" value="tcp" /><el-option label="UDP" value="udp" />
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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { systemApi } from '@/api/system'
import FeatureStatus from '@/components/common/FeatureStatus.vue'
import { networkApi } from '@/api/network'
import { useToast } from '@/composables/useToast'
import type { NetworkInterface, PortInfo } from '@/types/api'

const toast = useToast()
const features = ref<Array<{name:string;available:boolean}>>([])
async function fetchFeatures(){try{const f=await systemApi.getFeatures();features.value=Object.entries(f).filter(([k])=>['nmcli','netplan','firewall','sshfs'].includes(k)).map(([k,v])=>({name:k,available:!!v}))}catch{} }
const loading = ref(false)
const interfaces = ref<NetworkInterface[]>([])
const dns = ref<string[]>([])
const fw = ref<Record<string,any>>({})
const fwActiveTool = ref('')
const fwCmd = ref('')
const fwOutput = ref('')
const fwZones = ref<any>({ zones: [] })
const fwRichRules = ref<any[]>([])
async function loadFwZones() { try { fwZones.value = await networkApi.getFirewallZones() } catch {} }
async function loadFwRules(zone?: string) { try { fwRichRules.value = (await networkApi.getFirewallRichRules(zone)).rules || [] } catch {} }

// ── 网络诊断 ──
const diagHost = ref('')
const diagLoading = ref('')
const diagResult = ref<any>(null)
async function doPing() { if(!diagHost.value)return; diagLoading.value='ping'; try{diagResult.value=await networkApi.diagPing(diagHost.value)}catch{diagResult.value={error:'Ping 失败'}} finally{diagLoading.value=''} }
async function doTraceroute() { if(!diagHost.value)return; diagLoading.value='trace'; try{diagResult.value=await networkApi.diagTraceroute(diagHost.value)}catch{diagResult.value={error:'Traceroute 失败'}} finally{diagLoading.value=''} }
async function doDnsLookup() { if(!diagHost.value)return; diagLoading.value='dns'; try{diagResult.value=await networkApi.diagDns(diagHost.value)}catch{diagResult.value={error:'DNS 查询失败'}} finally{diagLoading.value=''} }
async function doPortScan() { if(!diagHost.value)return; diagLoading.value='scan'; try{diagResult.value=await networkApi.diagPortscan(diagHost.value)}catch{diagResult.value={error:'端口扫描失败'}} finally{diagLoading.value=''} }
async function doConnectivity() { diagLoading.value='conn'; try{diagResult.value=await networkApi.diagConnectivity()}catch{diagResult.value={error:'连通性检测失败'}} finally{diagLoading.value=''} }
const netManager = ref('')

const dnsPrimary = ref('')
const dnsBackup = ref('')
const dnsSaving = ref(false)

const ports = ref<PortInfo[]>([])
const portsLoading = ref(false)

const showAllowPort = ref(false)
const showDenyPort = ref(false)
const portForm = ref({ port: '', protocol: 'tcp' })

// IP
const showIpDialog = ref(false)
const ipIface = ref('')
const ipMode = ref('dhcp')
const ipAddr = ref('')
const ipMask = ref('24')
const ipGw = ref('')
const ipDns = ref('')

async function openIpDialog(row: NetworkInterface) {
  ipIface.value = row.name
  ipAddr.value = row.ipv4[0] || ''
  // Try to fetch actual IP config from backend for pre-fill
  try {
    const cfg = await networkApi.getIfaceIpMode(ipIface.value)
    if (cfg) {
      ipMode.value = cfg.mode || (row.ipv4.length > 0 ? 'static' : 'dhcp')
      ipMask.value = cfg.netmask || '24'
      ipGw.value = cfg.gateway || ''
      ipDns.value = cfg.dns || ''
    }
  } catch {
    ipMode.value = row.ipv4.length > 0 ? 'static' : 'dhcp'
    ipMask.value = '24'; ipGw.value = ''; ipDns.value = ''
  }
  showIpDialog.value = true
}
async function applyIpConfig() {
  try {
    const r = ipMode.value === 'dhcp'
      ? await networkApi.setDhcp(ipIface.value)
      : await networkApi.setStaticIp(ipIface.value, ipAddr.value, ipMask.value, ipGw.value, ipDns.value)
    toast.show(r.message, r.success ? 'success' : 'error')
    if (r.success) { showIpDialog.value = false; load() }
  } catch { toast.error('操作失败') }
}

// Bonding
const bondData = ref<{ bonds: any[]; slaves: string[]; modes: Record<string, string> }>({ bonds: [], slaves: [], modes: {} })
const bondName = ref('bond0'); const bondMode = ref('1'); const bondSlaves = ref<string[]>([])
async function loadBonds() { try { bondData.value = await networkApi.getBonds() } catch { toast.error("加载 Bond 信息失败") } }
async function doCreateBond() { try { const r = await networkApi.createBond(bondName.value, bondSlaves.value, bondMode.value); toast.show(r.message, r.success?'success':'error'); if(r.success){ bondSlaves.value=[]; await loadBonds() } } catch { toast.error('创建失败') } }
async function doDeleteBond(name: string) { try { const r = await networkApi.deleteBond(name); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadBonds() } catch { toast.error('删除失败') } }

// Advanced networking
const advTab = ref('vlan')
const vlanData = ref<any[]>([]); const vlanParent = ref(''); const vlanId = ref('')
async function loadVlans() { try { vlanData.value = (await networkApi.getVlans()).vlans||[] } catch { toast.error('加载 VLAN 信息失败') } }
async function doCreateVlan() { try { const r = await networkApi.createVlan(vlanParent.value, parseInt(vlanId.value)); toast.show(r.message, r.success?'success':'error'); if(r.success){ vlanId.value=''; await loadVlans() } } catch { toast.error('创建失败') } }
async function doDeleteVlan(name: string) { try { const r = await networkApi.deleteVlan(name); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadVlans() } catch { toast.error('删除失败') } }

const bridgeData = ref<any[]>([]); const bridgeName = ref('br0'); const brAddMember = ref<Record<string,string>>({})
async function loadBridges() { try { bridgeData.value = (await networkApi.getBridges()).bridges||[] } catch { toast.error('加载 Bridge 信息失败') } }
async function doCreateBridge() { try { const r = await networkApi.createBridge(bridgeName.value); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadBridges() } catch { toast.error('创建失败') } }
async function doBridgeAdd(br: string) { try { const iface = brAddMember.value[br]; if(!iface) return; const r = await networkApi.bridgeAddMember(br, iface); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadBridges() } catch { toast.error('操作失败') } }
async function doDeleteBridge(name: string) { try { const r = await networkApi.deleteBridge(name); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadBridges() } catch { toast.error('删除失败') } }

const routeData = ref<any[]>([]); const routeDst = ref(''); const routeGw = ref(''); const routeDev = ref('')
async function loadRoutes() { try { routeData.value = (await networkApi.getRoutes()).routes||[] } catch { toast.error('加载路由表失败') } }
async function doAddRoute() { try { const r = await networkApi.addRoute(routeDst.value, routeGw.value, routeDev.value); toast.show(r.message, r.success?'success':'error'); if(r.success){ routeDst.value=''; routeGw.value=''; routeDev.value=''; await loadRoutes() } } catch { toast.error('添加失败') } }
async function doDeleteRoute(row: any) { try { const r = await networkApi.deleteRoute(row.dst, row.gateway); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadRoutes() } catch { toast.error('删除失败') } }

const wgAvailable = ref(false); const wgData = ref<any[]>([]); const wgName = ref('wg0')
async function loadWireguard() { try { wgAvailable.value = (await networkApi.checkWireguard()).available; wgData.value = (await networkApi.getWireguardList()).interfaces||[] } catch { toast.error('加载 WireGuard 信息失败') } }
async function doCreateWg() { try { const r = await networkApi.createWireguard(wgName.value); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadWireguard() } catch { toast.error('创建失败') } }
async function doDeleteWg(name: string) { try { const r = await networkApi.deleteWireguard(name); toast.show(r.message, r.success?'success':'error'); if(r.success) await loadWireguard() } catch { toast.error('删除失败') } }

async function load() {
  loading.value = true
  try {
    const [ifaces, dnsRes, fwRes] = await Promise.all([networkApi.getInterfaces(), networkApi.getDns(), networkApi.getFirewall()])
    interfaces.value = ifaces; dns.value = dnsRes.dns; fw.value = fwRes
    if (fwRes?.active) fwActiveTool.value = fwRes.active
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
    if (res.success) { toast.success(`接口 ${name} ${action==='up'?'已启用':action==='down'?'已禁用':'已重启'}`); load() }
    else toast.warning(res.message || '操作失败')
  } catch (e: any) { toast.error(e.response?.data?.message || '操作失败') }
}

async function viewRules() {
  const tool = fwActiveTool.value || fw.value?.active || 'ufw'
  try {
    const res = await networkApi.getFirewallRules(tool)
    fwOutput.value = res.rules || '无输出'
  } catch (e: any) { fwOutput.value = '错误: ' + (e.response?.data?.message || e.message) }
}

async function loadNetworkManager() {
  try { netManager.value = (await networkApi.getNetworkManager()).manager } catch { toast.error("加载网络管理器信息失败") }
}

async function allowPort() {
  if (!portForm.value.port) { toast.warning('请输入端口号'); return }
  try {
    const res = await networkApi.fwAllow(portForm.value.port, portForm.value.protocol)
    if (res.success) { toast.success('端口已允许'); showAllowPort.value = false; portForm.value.port = '' }
    else toast.warning(res.message || '操作失败')
  } catch (e: any) { toast.error(e.response?.data?.message || '操作失败') }
}

async function denyPort() {
  if (!portForm.value.port) { toast.warning('请输入端口号'); return }
  try {
    const res = await networkApi.fwDeny(portForm.value.port, portForm.value.protocol)
    if (res.success) { toast.success('端口已禁止'); showDenyPort.value = false; portForm.value.port = '' }
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
  try { ports.value = (await networkApi.getPorts()).ports } catch { toast.error('加载端口失败') }
  finally { portsLoading.value = false }
}

// Auto-refresh
const autoRefresh = ref(false)
let _refreshTimer: ReturnType<typeof setInterval> | null = null
function toggleAutoRefresh(val: boolean) {
  if (val) _refreshTimer = setInterval(() => { load(); loadFwZones() }, 30000)
  else { if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null } }
}
onMounted(() => { load(); loadBonds(); loadNetworkManager(); loadVlans(); loadBridges(); loadRoutes(); loadWireguard(); loadFwZones(); fetchFeatures() })
onBeforeUnmount(() => { if (_refreshTimer) clearInterval(_refreshTimer) })
</script>

<style scoped>
.font-mono { font-family: 'JetBrains Mono', monospace; }

.iface-card { transition: all 0.15s ease; }
.iface-card:hover { border-color: var(--accent); }
.iface-card.down { opacity: 0.6; }

.status-dot {
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
  background: var(--text-2);
}
.status-dot.up { background: var(--green); box-shadow: 0 0 4px var(--green); }
.status-dot.down { background: var(--red); }

.iface-info {
  display: flex; flex-direction: column; gap: 3px;
  font-size: 12px; line-height: 1.5;
}
.info-row {
  display: flex; align-items: baseline; gap: 6px;
  min-width: 0;
}
.info-label {
  color: var(--text-2); font-size: 11px; flex-shrink: 0;
  min-width: 28px; text-align: right;
}
.truncate {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
</style>
