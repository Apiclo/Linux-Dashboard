"""Optimization profiles, service tuning, and quick kernel params."""
from typing import Dict, List, Optional, Tuple
from utils.helpers import run_cmd
from .sysctl import set_sysctl_param


# ── Service Optimization ──

COMMON_UNNECESSARY_SERVICES = [
    {"name": "cups", "desc": "打印服务", "safe": True, "warning": "如果有打印机或打印服务器需求请勿禁用"},
    {"name": "bluetooth", "desc": "蓝牙服务", "safe": True, "warning": "如果有蓝牙IoT设备请勿禁用"},
    {"name": "avahi-daemon", "desc": "mDNS/DNS-SD 服务", "safe": True, "warning": "如果有本地网络发现需求请勿禁用"},
    {"name": "ModemManager", "desc": "调制解调器管理", "safe": True, "warning": "如果有蜂窝网络设备请勿禁用"},
    {"name": "accounts-daemon", "desc": "用户账户服务", "safe": True, "warning": "某些桌面环境需要此服务"},
]


def get_service_optimization() -> List[Dict]:
    """Check which unnecessary services are running."""
    result = []
    for svc in COMMON_UNNECESSARY_SERVICES:
        _, code = run_cmd(f"systemctl is-enabled {svc['name']} 2>/dev/null")
        enabled = code == 0
        _, code2 = run_cmd(f"systemctl is-active {svc['name']} 2>/dev/null")
        active = code2 == 0
        result.append({**svc, "enabled": enabled, "active": active})
    return result


def optimize_services(svc_names: Optional[List[str]] = None) -> List[Dict]:
    """Disable common unnecessary services for server use.
    If svc_names is provided, only disable those specific services."""
    results = []
    for svc in COMMON_UNNECESSARY_SERVICES:
        if svc["safe"]:
            if svc_names is not None and svc["name"] not in svc_names:
                continue
            out, code = run_cmd(f"sudo systemctl disable --now {svc['name']} 2>/dev/null")
            results.append({"name": svc["name"], "success": code == 0})
    return results


# ── Quick Kernel Parameters ──

QUICK_KERNEL_PARAMS = {
    "vm.swappiness": {"desc": "Swap 倾向 (0=尽量不用, 100=积极使用)", "recommended": "10", "type": "range", "min": 0, "max": 100},
    "net.core.somaxconn": {"desc": "最大连接队列长度", "recommended": "65535", "type": "number"},
    "net.ipv4.tcp_max_syn_backlog": {"desc": "SYN 队列最大长度", "recommended": "65535", "type": "number"},
    "fs.file-max": {"desc": "系统最大文件描述符数", "recommended": "6553500", "type": "number"},
    "vm.overcommit_memory": {"desc": "内存过量分配 (0=启发式, 1=总是允许, 2=不超过swap+RAM*比率)", "recommended": "1", "type": "select", "options": ["0", "1", "2"]},
}


def get_quick_kernel_params() -> List[Dict]:
    """Get current values of common kernel params."""
    result = []
    for key, meta in QUICK_KERNEL_PARAMS.items():
        current, _ = run_cmd(f"sysctl -n {key} 2>/dev/null")
        result.append({"key": key, "current": current.strip(), **meta})
    return result


def apply_quick_kernel_params(params: Dict[str, str]) -> List[Dict]:
    """Apply kernel parameter values."""
    results = []
    for key, value in params.items():
        if key not in QUICK_KERNEL_PARAMS:
            results.append({"key": key, "success": False, "message": "Unknown parameter"})
            continue
        out, code = set_sysctl_param(key, value)
        results.append({"key": key, "success": code == 0, "message": out})
    return results


# ── 系统优化方案（场景化） ──

OPTIMIZATION_PROFILES = {
    "server": {
        "label": "服务器优化",
        "desc": "减少桌面服务开销，优化网络和内存参数，适合无头服务器环境",
        "sysctl": {
            "vm.swappiness": "10",
            "vm.vfs_cache_pressure": "50",
            "net.core.somaxconn": "65535",
            "net.core.netdev_max_backlog": "65535",
            "net.ipv4.tcp_max_syn_backlog": "8192",
            "net.ipv4.tcp_fastopen": "3",
            "fs.file-max": "6553500",
            "fs.inotify.max_user_instances": "8192",
        },
        "services_to_disable": [
            "cups", "cups-browsed", "bluetooth",
            "avahi-daemon", "ModemManager",
        ],
    },
    "desktop": {
        "label": "桌面优化",
        "desc": "保留桌面服务，优化 inotify 和虚拟内存，适合日常使用的桌面环境",
        "sysctl": {
            "vm.swappiness": "60",
            "fs.inotify.max_user_watches": "524288",
            "fs.inotify.max_user_instances": "1024",
        },
        "services_to_disable": [],
    },
}


def get_optimization_preview(profile: str) -> Dict:
    """预览某个优化方案将要变更的内容（不实际执行）。"""
    if profile not in OPTIMIZATION_PROFILES:
        return {"success": False, "message": f"Unknown profile: {profile}"}

    cfg = OPTIMIZATION_PROFILES[profile]
    sysctl_changes = []
    for key, recommended in cfg["sysctl"].items():
        current, _ = run_cmd(f"sysctl -n {key} 2>/dev/null")
        current = current.strip()
        sysctl_changes.append({
            "key": key,
            "current": current,
            "recommended": recommended,
            "will_change": current != recommended,
        })

    svc_changes = []
    for svc_name in cfg.get("services_to_disable", []):
        _, code = run_cmd(f"systemctl is-enabled {svc_name} 2>/dev/null")
        enabled = code == 0
        _, code2 = run_cmd(f"systemctl is-active {svc_name} 2>/dev/null")
        active = code2 == 0
        svc_changes.append({
            "name": svc_name,
            "enabled": enabled,
            "active": active,
            "will_disable": enabled or active,
        })

    return {
        "success": True,
        "profile": profile,
        "label": cfg["label"],
        "desc": cfg["desc"],
        "sysctl_changes": sysctl_changes,
        "svc_changes": svc_changes,
    }


def apply_optimization_profile(profile: str, sysctl_keys: Optional[List[str]] = None, svc_names: Optional[List[str]] = None) -> Dict:
    """应用某个优化方案。可指定仅应用部分项。"""
    if profile not in OPTIMIZATION_PROFILES:
        return {"success": False, "message": f"Unknown profile: {profile}"}

    cfg = OPTIMIZATION_PROFILES[profile]
    sysctl_results = []
    for key, value in cfg["sysctl"].items():
        # 如果指定了白名单，只应用白名单中的项
        if sysctl_keys is not None and key not in sysctl_keys:
            continue
        out, code = set_sysctl_param(key, value)
        sysctl_results.append({"key": key, "success": code == 0, "message": out})

    svc_results = []
    for svc_name in cfg.get("services_to_disable", []):
        if svc_names is not None and svc_name not in svc_names:
            continue
        out, code = run_cmd(f"sudo systemctl disable --now {svc_name} 2>/dev/null")
        svc_results.append({"name": svc_name, "success": code == 0})

    return {
        "success": True,
        "profile": profile,
        "sysctl_results": sysctl_results,
        "svc_results": svc_results,
    }


# ── 常用引导参数预设 ──

BOOT_PARAM_PRESETS = {
    "quiet_boot": {
        "label": "静默启动",
        "params": "quiet splash",
        "desc": "隐藏内核日志，显示启动画面",
    },
    "verbose_boot": {
        "label": "详细启动",
        "params": "",
        "desc": "显示所有内核日志（移除 quiet splash）",
    },
    "performance": {
        "label": "性能优化",
        "params": "mitigations=off transparent_hugepage=always elevator=mq-deadline",
        "desc": "禁用 CPU 漏洞缓解 + 透明大页 + mq-deadline",
    },
    "virtualization": {
        "label": "虚拟化主机",
        "params": "intel_iommu=on amd_iommu=on iommu=pt kvm.ignore_msrs=1 vfio-pci.ids=",
        "desc": "启用 IOMMU + KVM + VFIO（需根据硬件调整 vfio-pci.ids）",
    },
    "security": {
        "label": "安全加固",
        "params": "mitigations=auto lockdown=confidentiality module.sig_enforce=1",
        "desc": "启用所有 CPU 漏洞缓解 + 内核锁定 + 模块签名",
    },
    "low_latency": {
        "label": "低延迟",
        "params": "preempt=full nohz=on rcu_nocbs=all idle=poll",
        "desc": "完全抢占内核 + 无滴答 + RCU 隔离（实时场景）",
    },
}


# ═══════════════════ 内核参数配置文件管理 ═══════════════════

import os as _os
import json as _json
import time as _time

_SYSPROF_DIR = _os.path.expanduser("~/.tuxtacklebox/kernel_profiles")


def save_kernel_profile(name: str, params: List[Dict] = None) -> Dict:
    """保存当前内核参数为配置文件。"""
    _os.makedirs(_SYSPROF_DIR, exist_ok=True)
    safe_name = "".join(c for c in name if c.isalnum() or c in "._-") or "profile"
    path = _os.path.join(_SYSPROF_DIR, f"{safe_name}.json")

    if params is None:
        # Save current sysctl state
        from .sysctl import get_sysctl_params
        params_data = get_sysctl_params()
        params = params_data if isinstance(params_data, list) else []

    profile = {
        "name": safe_name,
        "created": _time.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": int(_time.time()),
        "params": params,
        "count": len(params),
    }
    try:
        with open(path, 'w') as f:
            _json.dump(profile, f, indent=2)
        return {"success": True, "name": safe_name, "path": path, "count": profile["count"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_kernel_profiles() -> List[Dict]:
    """列出已保存的内核参数配置文件。"""
    if not _os.path.isdir(_SYSPROF_DIR):
        return []
    profiles = []
    for fname in sorted(_os.listdir(_SYSPROF_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        path = _os.path.join(_SYSPROF_DIR, fname)
        try:
            with open(path) as f:
                p = _json.load(f)
                profiles.append(p)
        except Exception:
            profiles.append({"name": fname.replace(".json", ""), "error": "无法读取"})
    return profiles


def load_kernel_profile(name: str) -> Dict:
    """加载内核参数配置文件。"""
    safe_name = "".join(c for c in name if c.isalnum() or c in "._-")
    path = _os.path.join(_SYSPROF_DIR, f"{safe_name}.json")
    if not _os.path.isfile(path):
        return {"success": False, "error": f"配置文件不存在: {safe_name}"}
    try:
        with open(path) as f:
            return _json.load(f)
    except Exception as e:
        return {"success": False, "error": str(e)}


def apply_kernel_profile(name: str) -> Dict:
    """应用内核参数配置文件。"""
    profile = load_kernel_profile(name)
    if profile.get("error"):
        return {"success": False, "error": profile["error"]}

    params = profile.get("params", [])
    applied = []
    failed = []
    for p in params:
        key = p.get("key", "")
        val = p.get("value", "")
        if key:
            try:
                set_sysctl_param(key, val)
                applied.append(key)
            except Exception:
                failed.append(key)

    return {
        "success": len(failed) == 0,
        "profile": name,
        "applied": len(applied),
        "failed": failed,
    }


def delete_kernel_profile(name: str) -> Dict:
    """删除内核参数配置文件。"""
    safe_name = "".join(c for c in name if c.isalnum() or c in "._-")
    path = _os.path.join(_SYSPROF_DIR, f"{safe_name}.json")
    if not _os.path.isfile(path):
        return {"success": False, "error": "配置文件不存在"}
    try:
        _os.remove(path)
        return {"success": True, "message": f"已删除: {safe_name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_kernel_profile(name: str) -> Dict:
    """比较配置文件参数与当前值。"""
    profile = load_kernel_profile(name)
    if profile.get("error"):
        return {"success": False, "error": profile["error"]}

    params = profile.get("params", [])
    from .sysctl import get_sysctl_params
    current_data = get_sysctl_params()
    current = {}
    if isinstance(current_data, list):
        for c in current_data:
            current[c.get("key", "")] = c.get("value", "")

    diffs = []
    for p in params:
        key = p.get("key", "")
        old_val = p.get("value", "")
        new_val = current.get(key, "(not found)")
        if str(old_val) != str(new_val):
            diffs.append({"key": key, "profile_value": old_val, "current_value": new_val})

    return {
        "name": name,
        "total_params": len(params),
        "differences": len(diffs),
        "diffs": diffs[:50],
    }
