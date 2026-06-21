# Linux Dashboard

一个简单的 Linux 系统监控面板，前后端分离架构。

> ⚠️ 本项目 Vibe Coding 生成，代码未经严格审查，仅供参考。

## 技术栈

- 前端：Vue 3 + TypeScript + Element Plus
- 后端：Flask + psutil
- 实时通信：WebSocket

## 运行

```bash
# 安装依赖
bash install.sh

# 启动
bash start.sh

# 停止
bash stop.sh
```

默认后端 `5000` 端口，前端 `5173` 端口，配置见 `config.json`。

## 项目结构

```
backend/    Flask 服务
frontend/   Vue 前端
config.json 配置文件
```
