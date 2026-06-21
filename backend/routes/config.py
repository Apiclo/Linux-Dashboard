"""Config routes."""
import os
from flask import Blueprint, jsonify
from utils.helpers import safe_api, validate_json, require_auth, validate_path, run_cmd, safe_temp_file, safe_quote

bp = Blueprint("config", __name__)

PRESETS = {
    "SSH": {
        "path": "/etc/ssh/sshd_config",
        "keys": [
            {"key": "Port", "desc": "监听端口", "type": "number"},
            {"key": "ListenAddress", "desc": "监听地址", "type": "text"},
            {"key": "PermitRootLogin", "desc": "Root 登录", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "PasswordAuthentication", "desc": "密码认证", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "PubkeyAuthentication", "desc": "公钥认证", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "PermitEmptyPasswords", "desc": "空密码登录", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "ChallengeResponseAuthentication", "desc": "质询认证", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "UsePAM", "desc": "使用 PAM", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "X11Forwarding", "desc": "X11 转发", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "PrintMotd", "desc": "显示 MOTD", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "TCPKeepAlive", "desc": "TCP KeepAlive", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "ClientAliveInterval", "desc": "心跳间隔(秒)", "type": "number"},
            {"key": "MaxStartups", "desc": "最大并发连接", "type": "text"},
        ],
    },
    "Git": {
        "path": "~/.gitconfig",
        "keys": [
            {"key": "user.name", "desc": "用户名", "type": "text"},
            {"key": "user.email", "desc": "邮箱", "type": "text"},
            {"key": "core.editor", "desc": "编辑器", "type": "text"},
            {"key": "core.autocrlf", "desc": "自动 CRLF", "type": "bool", "true_val": "true", "false_val": "false"},
            {"key": "init.defaultBranch", "desc": "默认分支名", "type": "text"},
        ],
    },
    "Bash": {"path": "~/.bashrc", "keys": []},
    "Zsh": {"path": "~/.zshrc", "keys": []},
    "Nginx": {
        "path": "/etc/nginx/nginx.conf",
        "keys": [
            {"key": "worker_processes", "desc": "工作进程数", "type": "number"},
            {"key": "worker_connections", "desc": "每进程连接数", "type": "number"},
        ],
    },
    "GRUB": {
        "path": "/etc/default/grub",
        "keys": [
            {"key": "GRUB_TIMEOUT", "desc": "选择超时(秒)", "type": "number"},
            {"key": "GRUB_CMDLINE_LINUX", "desc": "内核引导参数", "type": "text"},
            {"key": "GRUB_DISABLE_OS_PROBER", "desc": "禁用 OS 探测", "type": "bool", "true_val": "true", "false_val": "false"},
            {"key": "GRUB_DISABLE_RECOVERY", "desc": "禁用恢复模式", "type": "bool", "true_val": "true", "false_val": "false"},
            {"key": "GRUB_DISABLE_SUBMENU", "desc": "禁用子菜单", "type": "bool", "true_val": "true", "false_val": "false"},
        ],
    },
    "Fstab": {"path": "/etc/fstab", "keys": []},
    "Sysctl": {
        "path": "/etc/sysctl.conf",
        "keys": [
            {"key": "net.ipv4.ip_forward", "desc": "IP 转发", "type": "bool", "true_val": "1", "false_val": "0"},
            {"key": "net.ipv6.conf.all.disable_ipv6", "desc": "禁用 IPv6", "type": "bool", "true_val": "1", "false_val": "0"},
            {"key": "vm.swappiness", "desc": "Swap 倾向", "type": "number"},
        ],
    },
    "Docker": {
        "path": "/etc/docker/daemon.json",
        "keys": [],
    },
}


@bp.route("/api/config/presets")
@safe_api
@require_auth
def presets():
    return jsonify(PRESETS)


@bp.route("/api/config/read", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def read_config(data):
    path = os.path.expanduser(data["path"])
    ok, real = validate_path(path)
    if not ok: return jsonify({"success": False, "message": "Access denied"}), 403
    try:
        with open(real) as f:
            content = f.read()
        # Pre-parse values for the preset's keys so the frontend doesn't need to
        parsed = {}
        preset_name = data.get("preset", "")
        if preset_name and preset_name in PRESETS:
            for pk in PRESETS[preset_name]["keys"]:
                for line in content.splitlines():
                    s = line.strip()
                    if not s or s.startswith('#'):
                        continue
                    k = pk["key"]
                    if s.startswith(k + '='):
                        parsed[k] = s.split('=', 1)[1].strip().strip('"\'')
                        break
                    if s.startswith(k + ' '):
                        parsed[k] = s.split(None, 1)[1].strip().strip('"\'')
                        break
        return jsonify({"success": True, "content": content, "path": real, "parsed": parsed})
    except Exception as e: return jsonify({"success": False, "message": str(e)})


@bp.route("/api/config/save", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path", "content"])
def save_config(data):
    path = os.path.expanduser(data["path"])
    ok, real = validate_path(path)
    if not ok: return jsonify({"success": False, "message": "Access denied"}), 403
    try:
        tmp = safe_temp_file(suffix=".conf", content=data["content"])
        _, code = run_cmd(f"sudo cp {safe_quote(tmp)} {safe_quote(real)}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return jsonify({"success": code == 0, "path": real})
    except Exception as e: return jsonify({"success": False, "message": str(e)})


@bp.route("/api/config/setparam", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path", "key", "value"])
def setparam(data):
    path = os.path.expanduser(data["path"])
    ok, real = validate_path(path)
    if not ok: return jsonify({"success": False, "message": "Access denied"}), 403
    key, value = data["key"], data["value"]
    # 防御 newline 注入
    if '\n' in key or '\r' in key or '\n' in value or '\r' in value:
        return jsonify({"success": False, "message": "Newlines not allowed in key or value"}), 400
    try:
        content = ""
        if os.path.exists(real):
            with open(real) as f: content = f.read()
        lines = content.splitlines()
        found = False
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith(key + "="): lines[i] = f"{key}={value}"; found = True; break
            if s.startswith(key + " "): lines[i] = f"{key} {value}"; found = True; break
        if not found: lines.append(f"{key}={value}")
        new = "\n".join(lines) + "\n"
        tmp = safe_temp_file(suffix=".conf", content=new)
        _, code = run_cmd(f"sudo cp {safe_quote(tmp)} {safe_quote(real)}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return jsonify({"success": code == 0, "content": new})
    except Exception as e: return jsonify({"success": False, "message": str(e)})
