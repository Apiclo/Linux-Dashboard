#!/usr/bin/env python3
"""PenguinFu Backend — API Server v0.1.1-dev"""
import os
import re
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, session, request, send_from_directory, Response
from utils.tasks import OUTPUT_QUEUES, start_cleanup_thread, cancel_task
from utils.auth import authenticate, init_session_secret, require_auth

# ── Load config ──
_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
try:
    with open(_config_path) as f:
        CONFIG = json.load(f)
except Exception:
    CONFIG = {"backend": {"host": "0.0.0.0", "port": 5000, "debug": False}, "auth": {"session_lifetime": 86400}}

# ── Logging ──
# 优先写入项目目录（开发环境），不可写则回退到 ~/.penguinfu（AppImage / 生产）
_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
try:
    os.makedirs(_log_dir, exist_ok=True)
    # 测试可写
    _test = os.path.join(_log_dir, ".write_test")
    with open(_test, "w") as f: f.write("")
    os.remove(_test)
except (OSError, PermissionError):
    _log_dir = os.path.expanduser("~/.penguinfu/logs")
    os.makedirs(_log_dir, exist_ok=True)

_handlers = [logging.StreamHandler()]
try:
    _handlers.append(logging.FileHandler(os.path.join(_log_dir, "backend.log"), mode="a"))
except (OSError, PermissionError):
    pass
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=_handlers)
log = logging.getLogger("backend")

# ── App ──
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

# 会话安全
_session_dir = os.path.expanduser("~/.penguinfu/sessions")
os.makedirs(_session_dir, mode=0o700, exist_ok=True)
app.config["SESSION_FILE_DIR"] = _session_dir
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = CONFIG.get("auth", {}).get("session_secure", False)  # 生产环境应设为 True
app.config["PERMANENT_SESSION_LIFETIME"] = CONFIG.get("auth", {}).get("session_lifetime", 86400)
os.makedirs("/tmp/penguinfu-uploads", exist_ok=True)
init_session_secret(app)

# ── Sudo access check ──
import subprocess as _sp
_sudo_ok = False
try:
    _r = _sp.run(["sudo", "-n", "true"], capture_output=True, timeout=5)
    _sudo_ok = _r.returncode == 0
except Exception:
    pass
if not _sudo_ok and os.geteuid() != 0:
    log.warning("⚠ Backend user has NO passwordless sudo and is NOT root. Write operations (mount, install, etc.) will FAIL.")
    log.warning("  Fix: run as root, OR add to /etc/sudoers.d/penguinfu:")
    log.warning(f"    {os.environ.get('USER', 'your-user')} ALL=(ALL) NOPASSWD: ALL")
else:
    log.info("✓ Sudo/root access verified")

# ── Register blueprints ──
from routes import system, network, services, disk, packages, config, gpu, offline, raid, rescue
app.register_blueprint(system.bp)
app.register_blueprint(network.bp)
app.register_blueprint(services.bp)
app.register_blueprint(disk.bp)
app.register_blueprint(packages.bp)
app.register_blueprint(config.bp)
app.register_blueprint(gpu.bp)
app.register_blueprint(offline.bp)
app.register_blueprint(raid.bp)
app.register_blueprint(rescue.bp)


# ── Global error handlers ──

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "message": "Not found"}), 404
    # SPA fallback
    if os.path.isdir(_dist_dir):
        return send_from_directory(_dist_dir, "index.html")
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "message": "Internal server error"}), 500


# ── Serve frontend dist in production ──
# PyInstaller 打包时，静态文件在 sys._MEIPASS
if getattr(sys, 'frozen', False):
    _dist_dir = os.path.join(sys._MEIPASS, "frontend", "dist")
else:
    _dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
_has_frontend = os.path.isdir(_dist_dir)


@app.route("/")
def index():
    if _has_frontend:
        return send_from_directory(_dist_dir, "index.html")
    return jsonify({"error": "Frontend not built. Run: cd frontend && npm run build"}), 404


@app.route("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    if _has_frontend and os.path.exists(os.path.join(_dist_dir, path)):
        return send_from_directory(_dist_dir, path)
    if _has_frontend:
        return send_from_directory(_dist_dir, "index.html")
    return jsonify({"error": "Not found"}), 404


# ── Auth endpoints ──

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ok, msg = authenticate(username, password)
    if ok:
        session.permanent = True
        session["authenticated"] = True
        session["username"] = username
        log.info(f"Login: {username} from {request.remote_addr}")
        return jsonify({"success": True, "message": msg, "username": username})
    log.warning(f"Login failed: {username} from {request.remote_addr}")
    return jsonify({"success": False, "message": msg}), 401


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    user = session.get("username", "unknown")
    session.clear()
    log.info(f"Logout: {user}")
    return jsonify({"success": True, "message": "已登出"})


@app.route("/api/auth/status")
def api_auth_status():
    if session.get("authenticated"):
        return jsonify({"authenticated": True, "username": session.get("username")})
    return jsonify({"authenticated": False})


@app.route("/api/health")
def health():
    from core.system import _get_uptime
    from datetime import datetime
    return {"status": "ok", "uptime": _get_uptime(), "timestamp": datetime.now().isoformat()}


@app.route("/api/stream/<task_id>")
@require_auth
def stream(task_id):
    # Validate task_id format (alphanumeric, underscore, dash only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', task_id) or len(task_id) > 100:
        return jsonify({"success": False, "message": "Invalid task ID"}), 400
    def generate():
        q = OUTPUT_QUEUES.get(task_id)
        if not q:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Task not found'})}\n\n"
            return
        heartbeat = 0
        while True:
            try:
                msg_type, data = q.get(timeout=30)
                heartbeat = 0
                if msg_type == "output":
                    yield f"data: {json.dumps({'type': 'output', 'line': data})}\n\n"
                elif msg_type == "done":
                    yield f"data: {json.dumps({'type': 'done', 'code': data})}\n\n"
                    break
                elif msg_type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': data})}\n\n"
            except Exception:
                heartbeat += 1
                if heartbeat > 20:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout'})}\n\n"
                    break
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        OUTPUT_QUEUES.pop(task_id, None)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/task/cancel/<task_id>", methods=["POST"])
@require_auth
def task_cancel(task_id):
    ok = cancel_task(task_id)
    return {"success": ok, "message": "Cancelled" if ok else "Not found"}


# ── WebSocket Chroot Shell ──
try:
    from flask_sock import Sock
    sock = Sock(app)

    @sock.route('/ws/chroot')
    def chroot_shell(ws):
        """WebSocket 双向 chroot 交互终端（需认证）。"""
        # 认证检查
        if not session.get("authenticated"):
            ws.send("\r\n\x1b[31m[ERROR] 请先登录后再使用 chroot 终端\x1b[0m\r\n")
            ws.close()
            return

        import pty
        import select
        import subprocess
        import shlex
        import os as _os
        from core.rescue import prepare_chroot, teardown_chroot

        proc = None
        root = "/mnt"
        shell = "/bin/bash"
        fd = None

        try:
            # 等待初始消息
            init_data = ws.receive(timeout=10)
            if init_data:
                import json as _json
                try:
                    init = _json.loads(init_data)
                    root = init.get("root", "/mnt")
                    shell = init.get("shell", "/bin/bash")
                except Exception:
                    pass

            # 路径安全检查：只允许 /mnt/ 和 /media/ 下的目录
            real_root = _os.path.realpath(_os.path.expanduser(root))
            allowed = False
            for prefix in ["/mnt/", "/media/"]:
                if real_root == prefix.rstrip("/") or real_root.startswith(prefix):
                    allowed = True
                    break
            if not allowed:
                ws.send(f"\r\n\x1b[31m[ERROR] 不允许的 chroot 路径: {root}（仅允许 /mnt/ 和 /media/ 下）\x1b[0m\r\n")
                ws.close()
                return
            root = real_root

            # 准备 chroot 环境
            ok, msg = prepare_chroot(root)
            if not ok:
                ws.send(f"\r\n\x1b[31m[ERROR] {msg}\x1b[0m\r\n")
                return
            ws.send(f"\r\n\x1b[32m[INFO] Chroot 环境已准备: {root}\x1b[0m\r\n")

            # 分配 PTY 并启动 chroot shell
            pid, fd = pty.fork()
            if pid == 0:
                # 子进程
                os.chdir(root)
                os.chroot(root)
                os.execle(shell, shell, {"TERM": "xterm-256color", "HOME": "/root", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"})
                os._exit(1)

            # 父进程：双向转发
            import threading
            running = True

            def reader():
                nonlocal running
                while running:
                    try:
                        r, _, _ = select.select([fd], [], [], 0.1)
                        if r:
                            data = os.read(fd, 4096)
                            if not data:
                                break
                            ws.send(data.decode('utf-8', errors='replace'))
                    except Exception:
                        break

            t = threading.Thread(target=reader, daemon=True)
            t.start()

            while running:
                try:
                    msg = ws.receive(timeout=0.5)
                    if msg is None:
                        continue
                    if msg == "__CLOSE__":
                        running = False
                        break
                    os.write(fd, msg.encode('utf-8', errors='replace'))
                except Exception:
                    running = False
                    break

        except Exception as e:
            try:
                ws.send(f"\r\n\x1b[31m[ERROR] {e}\x1b[0m\r\n")
            except Exception:
                pass
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass
            # 清理 chroot 挂载
            try:
                ok2, msg2 = teardown_chroot(root)
                ws.send(f"\r\n\x1b[33m[INFO] Chroot 环境已清理\x1b[0m\r\n")
            except Exception:
                pass

except ImportError:
    print("[WARN] flask-sock not installed — WebSocket chroot disabled. pip install flask-sock")
    sock = None


# ── Main ──
if __name__ == "__main__":
    host = CONFIG.get("backend", {}).get("host", "0.0.0.0")
    port = CONFIG.get("backend", {}).get("port", 5000)
    debug = CONFIG.get("backend", {}).get("debug", False)

    start_cleanup_thread()

    print()
    print("  ╔═══════════════════════════════════════════════╗")
    print("  ║           PenguinFu Backend v0.1.1-dev          ║")
    print("  ╠═══════════════════════════════════════════════╣")
    print(f"  ║  API:     http://127.0.0.1:{port:<5}              ║")
    print(f"  ║  Auth:    Linux PAM                            ║")
    if os.path.isdir(_dist_dir):
        print(f"  ║  Frontend: http://127.0.0.1:{port:<5}             ║")
    else:
        print(f"  ║  Frontend: http://localhost:5173 (dev mode)    ║")
    print("  ╚═══════════════════════════════════════════════╝")
    print()

    app.run(host=host, port=port, debug=debug, threaded=True)
