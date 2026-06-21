#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PenguinFu — 安装辅助脚本
# 将打包好的 dist/penguinfu/ 目录安装到 /opt/penguinfu
# 前提: 已执行 ./build.sh 完成打包
# ═══════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_SRC="$SCRIPT_DIR/dist/penguinfu"
INSTALL_DIR="/opt/penguinfu"

echo "PenguinFu — 安装到 $INSTALL_DIR"

if [ ! -f "$PKG_SRC/penguinfu" ]; then
    echo "错误: 未找到打包产物，请先执行 ./build.sh"
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "需要 root 权限"
    exit 1
fi

# 安装
rm -rf "$INSTALL_DIR"
cp -r "$PKG_SRC" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/penguinfu"

# 全局命令
ln -sf "$INSTALL_DIR/penguinfu" /usr/local/bin/penguinfu

echo ""
echo "安装完成。"
echo "  启动: penguinfu"
echo "  访问: http://127.0.0.1:5000"
echo "  配置: $INSTALL_DIR/config.json"
echo "  日志: $INSTALL_DIR/logs/"
