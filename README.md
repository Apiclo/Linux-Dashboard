# TuxTackleBox 🐧🥋

> Linux 系统管理工具箱 — 一个文件，全部搞定。


## 功能概览

### 系统管理
- **系统参数** — 主机名 / 时区 / 语言 / SSH 配置 / Hosts 编辑
- **Swap 管理** — 创建 / 关闭 / 查看
- **内核参数** — sysctl 搜索 / 编辑，快速参数批量设置
- **内核模块** — 加载 / 卸载 / 搜索
- **引导与内核调优** — GRUB 默认内核选择 / cmdline 预设（性能/虚拟化/安全/低延迟）/ CPU 调频器 / I/O 调度器
- **系统优化方案** — 服务器优化 / 桌面优化，逐项预览后应用
- **用户管理** — 添加 / 删除 / 改密
- **系统日志** — journalctl 按服务/级别查询
- **NTP 时间同步** — 启用 / 禁用 / 状态查询
- **Ulimits 资源限制** — 查看 / 编辑

### 服务管理
- systemd 服务列表 / 搜索 / 过滤
- 启动 / 停止 / 重启 / 启用 / 禁用
- 服务日志实时查看

### 网络管理
- **网络接口** — 状态 / IP / MAC / 速度 / 启用禁用
- **IP 配置** — 静态 IP / DHCP，自动适配 NetworkManager 或 ip 命令
- **网络绑定 (Bond)** — 创建 / 删除，支持 mode 0-6
- **防火墙** — 端口放行/禁止，自定义命令执行
- **DNS 配置** — 查看 / 修改
- **端口监听** — 实时查看

### 磁盘管理
- 块设备列表（树形展开）
- 磁盘使用率（进度条）
- 挂载 / 卸载
- fstab 编辑
- RAID 管理 — 创建 / 停止 / 移除 / 详情

### GPU 驱动管理
- **环境检测** — GPU 型号 / 内核 / 头文件 / SecureBoot / nouveau 状态
- **兼容性检查** — 组件 / 警告 / 错误
- **NVIDIA 驱动安装** — 仓库安装 / .run 安装 / 离线包安装 / 生成离线包
- **CUDA 安装** — 分步设置源 + 安装，自动按发行版选择仓库
- **AMD / Intel 开源驱动**
- **自定义命令执行**

### 软件包管理
- 发行版自动检测（apt / dnf / pacman / zypper 等）
- 软件搜索 / 安装 / 卸载 / 系统更新
- 常用软件一键安装（浏览器 / 编辑器 / 终端 / 开发工具）
- 实时 SSE 输出

### 配置编辑
- 预设配置模板 — SSH / GRUB / Nginx / Sysctl / Docker / Git
- yes/no 开关切换 / 数字输入 / 文本编辑
- 自定义路径文件编辑
- 配置保存（sudo 写入）

### 系统救援
- **ISO 本地源管理** — 挂载 ISO / 按发行版配置本地源（apt/dnf/zypper/pacman）/ 浏览内容 / 卸载
- **SFTP 远程挂载** — 挂载 / 卸载 / 状态查看
- **Chroot 救援** — 挂载虚拟文件系统 / xterm.js 交互终端（WebSocket）

### 存储工具
- **LVM** — PV / VG / LV 创建 / 扩展 / 删除 / 状态
- **Btrfs** — 子卷 / 快照 / scrub / balance
- **文件系统检查** — ext4 / XFS / Btrfs 检查和修复
- **在线扩容** — ext4 / XFS / Btrfs resize
- **SMART** — 磁盘健康状态 / 属性详情
- **ZFS** — 池状态

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + TypeScript + Element Plus + Tailwind CSS v4 + xterm.js |
| 后端 | Flask + psutil + PAM + SSE 实时流 |
| 交互终端 | WebSocket + PTY 分配 |
| 认证 | Linux PAM（系统用户登录） |
| 主题 | 暗色 / 亮色切换 |

## 快速开始

```bash
# 开发模式（前端热更新 + 后端）
./start.sh

# 生产模式（后端服务前端静态文件）
./start.sh --prod
```

- 后端 API：`http://127.0.0.1:5000`
- 配置：`config.json`

## 打包分发

```bash
# venv 自包含目录（需 Python 3.8+）
./build.sh

# PyInstaller onedir（无需 Python）
./build.sh --binary

# AppImage 单文件（跨发行版，需在旧 glibc 环境构建）
./build-docker.sh        # Docker 内构建（glibc 2.27+）
./build.sh --appimage    # 本地构建（同构建机 glibc）

# 查看依赖清单
./build.sh --deps
```

## 安装到系统（可选）

```bash
sudo ./install.sh
# → /opt/tuxtacklebox/ + /usr/local/bin/tuxtacklebox
```

## 项目结构

```
backend/
├── main.py              # Flask 入口 + WebSocket
├── core/                # 业务逻辑层
│   ├── system.py        # 系统参数 / 引导 / 内核
│   ├── gpu.py           # GPU 检测 / 驱动 / CUDA
│   ├── network.py       # 网络 / IP / Bonding
│   ├── storage.py       # LVM / Btrfs / FS / SMART
│   ├── rescue.py        # ISO / SFTP / Chroot
│   ├── disk.py          # 块设备 / 挂载 / fstab
│   ├── raid.py          # mdadm RAID
│   ├── package.py       # 软件包管理
│   ├── services.py      # systemd 服务
│   └── distro.py        # 发行版检测
├── routes/              # Flask Blueprint
└── utils/               # 基础设施（认证/tasks/helpers）

frontend/
├── src/
│   ├── views/           # 页面组件（11 个视图）
│   ├── components/      # 子组件（终端/布局/系统面板）
│   ├── api/             # API 客户端
│   ├── composables/     # 组合式函数
│   ├── types/           # TypeScript 类型
│   └── styles/          # 全局 CSS 变量 + 主题
└── dist/                # 构建产物

build.sh                  # 打包脚本（3 种模式）
build-docker.sh           # Docker 内构建（兼容旧 glibc）
install.sh                # 系统安装脚本
start.sh / stop.sh        # 启停脚本
config.json               # 运行时配置
```

## 系统要求

| 组件 | 最低版本 |
|------|---------|
| Python | ≥ 3.8 |
| Node.js (仅开发) | ≥ 18 |
| 操作系统 | Linux（systemd / PAM） |
| 权限 | passwordless sudo（写操作） |
