#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PenguinFu — 打包脚本
#   ./build.sh             → venv 自包含目录（最可移植，推荐）
#   ./build.sh --binary    → PyInstaller onedir 目录
#   ./build.sh --appimage  → 单个 .AppImage 文件（跨发行版通用）
#   ./build.sh --deps      → 仅列出依赖清单
# ═══════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

DIST_DIR="$SCRIPT_DIR/dist"
BINARY_NAME="penguinfu"
MODE="${1:-venv}"

echo ""
echo "  ╔═══════════════════════════════════════════════╗"
echo "  ║       PenguinFu — Package Builder             ║"
echo "  ╚═══════════════════════════════════════════════╝"
echo ""

# ── 依赖清单 ──
if [ "$MODE" = "--deps" ]; then
    echo "运行时依赖:"
    echo "  - python >= 3.8"
    echo "  - pip3"
    echo ""
    echo "Python 包 (backend/requirements.txt):"
    cat "$SCRIPT_DIR/backend/requirements.txt"
    echo ""
    echo "前端构建依赖 (frontend/package.json):"
    echo "  - nodejs >= 18"
    echo "  - npm"
    echo ""
    echo "AppImage 构建依赖:"
    echo "  - file (libmagic)"
    echo "  - appimagetool 自动下载"
    exit 0
fi

# ── 清理 ──
rm -rf "$DIST_DIR" "$SCRIPT_DIR/build"
mkdir -p "$DIST_DIR"

# ── 前端（所有模式都需要） ──
echo "[1/3] 构建前端..."
if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    cd "$SCRIPT_DIR/frontend" && npm install --silent && cd "$SCRIPT_DIR"
fi
FRONTEND_DIST="$SCRIPT_DIR/build/frontend/dist"
cd "$SCRIPT_DIR/frontend" && npx vite build --outDir "$FRONTEND_DIST" --emptyOutDir && cd "$SCRIPT_DIR"
echo "  ✓ 前端就绪"

# ── 模式: venv 自包含目录 ──
if [ "$MODE" = "--appimage" ]; then
    # AppImage 先从 venv 目录构建 AppDir
    echo "[2/3] 创建虚拟环境..."
    APPDIR="$SCRIPT_DIR/build/AppDir"
    VENV_DIR="$APPDIR/venv"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip -q 2>/dev/null
    pip install -r "$SCRIPT_DIR/backend/requirements.txt" -q
    deactivate
    echo "  ✓ venv 就绪"

    echo "[3/3] 组装 AppDir → AppImage..."
    cp -r "$SCRIPT_DIR/backend" "$APPDIR/"
    mkdir -p "$APPDIR/frontend" && cp -r "$FRONTEND_DIST" "$APPDIR/frontend/dist"
    cp "$SCRIPT_DIR/config.json" "$APPDIR/"
    rm -rf "$APPDIR/backend/venv" "$APPDIR/backend/__pycache__"
    find "$APPDIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

    # AppRun
    cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/venv/bin:$PATH"
exec "$HERE/venv/bin/python" "$HERE/backend/main.py" "$@"
APPRUN
    chmod +x "$APPDIR/AppRun"

    # .desktop
    cat > "$APPDIR/penguinfu.desktop" << 'DESKTOP'
[Desktop Entry]
Name=PenguinFu
Comment=System Management Toolbox
Exec=AppRun
Icon=penguinfu
Type=Application
Categories=System;
DESKTOP

    # 图标 (SVG 企鹅 + 扳手)
    cat > "$APPDIR/penguinfu.svg" << 'ICON'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <circle cx="64" cy="64" r="62" fill="#1a1a2e"/>
  <ellipse cx="52" cy="52" rx="18" ry="20" fill="#e6edf3"/>
  <ellipse cx="76" cy="52" rx="18" ry="20" fill="#e6edf3"/>
  <ellipse cx="64" cy="80" rx="28" ry="32" fill="#161b22"/>
  <ellipse cx="64" cy="82" rx="22" ry="24" fill="#e6edf3"/>
  <circle cx="52" cy="48" r="4" fill="#1a1a2e"/>
  <circle cx="76" cy="48" r="4" fill="#1a1a2e"/>
  <ellipse cx="64" cy="62" rx="8" ry="5" fill="#f85149"/>
  <rect x="20" y="90" width="24" height="6" rx="2" fill="#d29922"/>
  <rect x="84" y="90" width="24" height="6" rx="2" fill="#d29922"/>
  <text x="64" y="98" text-anchor="middle" font-size="10" fill="#58a6ff" font-family="Arial">PENGUINFU</text>
</svg>
ICON
    cp "$APPDIR/penguinfu.svg" "$APPDIR/.DirIcon"

    # 下载 appimagetool
    AIM="$SCRIPT_DIR/build/appimagetool"
    if [ ! -f "$AIM" ]; then
        echo "  下载 appimagetool..."
        wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O "$AIM" 2>/dev/null || \
        curl -sL "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -o "$AIM"
        chmod +x "$AIM"
    fi

    # 生成 AppImage
    ARCH=$(uname -m)
    "$AIM" "$APPDIR" "$DIST_DIR/$BINARY_NAME-$ARCH.AppImage" 2>&1 | tail -3
    rm -rf "$SCRIPT_DIR/build"
    SIZE=$(ls -lh "$DIST_DIR/"*.AppImage 2>/dev/null | awk '{print $5}')

    echo ""
    echo "  ╔═══════════════════════════════════════════════╗"
    echo "  ║  打包完成（AppImage）                         ║"
    echo "  ╠═══════════════════════════════════════════════╣"
    echo "  ║  大小:   $SIZE"
    echo "  ║  文件:   $DIST_DIR/$BINARY_NAME-$ARCH.AppImage"
    echo "  ╚═══════════════════════════════════════════════╝"
    echo ""
    echo "  使用: chmod +x $BINARY_NAME-*.AppImage && ./$BINARY_NAME-*.AppImage"
    echo "  跨发行版通用，无需安装"

elif [ "$MODE" != "--binary" ]; then
    # ── 模式: venv 自包含目录 ──
    echo "[2/3] 创建虚拟环境..."
    PKG_DIR="$DIST_DIR/$BINARY_NAME"
    VENV_DIR="$PKG_DIR/venv"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip -q 2>/dev/null
    pip install -r "$SCRIPT_DIR/backend/requirements.txt" -q
    deactivate
    echo "  ✓ venv 就绪"

    echo "[3/3] 组装..."
    cp -r "$SCRIPT_DIR/backend" "$PKG_DIR/"
    cp -r "$FRONTEND_DIST" "$PKG_DIR/frontend/dist"
    cp "$SCRIPT_DIR/config.json" "$PKG_DIR/"
    rm -rf "$PKG_DIR/backend/venv" "$PKG_DIR/backend/__pycache__"
    find "$PKG_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

    cat > "$PKG_DIR/$BINARY_NAME" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/venv/bin/python" "$DIR/backend/main.py" "$@"
LAUNCHER
    chmod +x "$PKG_DIR/$BINARY_NAME"
    echo "0.1.1-dev" > "$PKG_DIR/VERSION"
    rm -rf "$SCRIPT_DIR/build"
    SIZE=$(du -sh "$PKG_DIR" | cut -f1)
    echo ""
    echo "  ╔═══════════════════════════════════════════════╗"
    echo "  ║  打包完成（venv 自包含目录）                  ║"
    echo "  ╠═══════════════════════════════════════════════╣"
    echo "  ║  大小:   $SIZE"
    echo "  ║  路径:   $PKG_DIR/"
    echo "  ║  运行:   $PKG_DIR/$BINARY_NAME"
    echo "  ╚═══════════════════════════════════════════════╝"
    echo ""
    echo "  部署: 复制到目标机器即可，需 Python 3.8+"

else
    # ── 模式: PyInstaller onedir ──
    echo "[2/3] 准备构建 venv..."
    BUILD_VENV="$SCRIPT_DIR/build/venv"
    python3 -m venv "$BUILD_VENV"
    source "$BUILD_VENV/bin/activate"
    pip install --upgrade pip -q 2>/dev/null
    pip install -r "$SCRIPT_DIR/backend/requirements.txt" -q
    pip install pyinstaller -q
    echo "  ✓ 构建 venv 就绪"

    echo "[3/3] PyInstaller 打包 (onedir — 兼容旧 glibc)..."
    cd "$SCRIPT_DIR/backend"
    pyinstaller \
        --distpath "$DIST_DIR/app" \
        --workpath "$SCRIPT_DIR/build/pyinstaller" \
        --name "$BINARY_NAME" \
        --onedir \
        --add-data "$FRONTEND_DIST:frontend/dist" \
        --add-data "$SCRIPT_DIR/config.json:." \
        --hidden-import flask \
        --hidden-import psutil \
        --hidden-import pamela \
        --hidden-import flask_sock \
        --clean \
        --noconfirm \
        main.py 2>&1 | tail -5

    cd "$SCRIPT_DIR"
    rm -rf "$SCRIPT_DIR/build"

    cat > "$DIST_DIR/$BINARY_NAME" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/app/penguinfu/penguinfu" "$@"
LAUNCHER
    chmod +x "$DIST_DIR/$BINARY_NAME"
    cp "$SCRIPT_DIR/config.json" "$DIST_DIR/" 2>/dev/null || true

    SIZE=$(du -sh "$DIST_DIR" | cut -f1)
    echo ""
    echo "  ╔═══════════════════════════════════════════════╗"
    echo "  ║  打包完成（onedir）                            ║"
    echo "  ╠═══════════════════════════════════════════════╣"
    echo "  ║  大小:   $SIZE"
    echo "  ║  运行:   $DIST_DIR/$BINARY_NAME"
    echo "  ╚═══════════════════════════════════════════════╝"
    echo ""
    echo "  部署: 将 $DIST_DIR/ 整个目录复制到目标机器即可"
    echo "  无需 Python / glibc 版本限制"
fi
