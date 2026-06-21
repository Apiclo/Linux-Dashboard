"""Config file presets — defines editable parameters for common system config files.

Each preset has:
  - path:  Absolute (or ~-relative) path to the config file.
  - keys:  List of editable keys, each with:
      key       — config key name
      desc      — human-readable description
      type      — 'bool' | 'number' | 'text'
      true_val  — (bool only) value written when "on"
      false_val — (bool only) value written when "off"
"""

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
    "Journald": {
        "path": "/etc/systemd/journald.conf",
        "keys": [
            {"key": "SystemMaxUse", "desc": "最大磁盘使用", "type": "text"},
            {"key": "MaxFileSec", "desc": "日志保留时间", "type": "text"},
            {"key": "ForwardToSyslog", "desc": "转发到 syslog", "type": "bool", "true_val": "yes", "false_val": "no"},
            {"key": "Compress", "desc": "压缩日志", "type": "bool", "true_val": "yes", "false_val": "no"},
        ],
    },
    "Hostname": {"path": "/etc/hostname", "keys": []},
    "Resolv": {"path": "/etc/resolv.conf", "keys": []},
    "Limits": {"path": "/etc/security/limits.conf", "keys": []},
    "Motd": {"path": "/etc/motd", "keys": []},
}
