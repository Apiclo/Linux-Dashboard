"""Service operations — delegates to the detected init system manager."""
from typing import Dict, List, Tuple
from core.service_manager import get_manager
from utils.helpers import run_cmd, safe_quote


def get_services() -> List[Dict]:
    return get_manager().get_services()


def service_action(name: str, action: str) -> Tuple[str, int]:
    return get_manager().service_action(name, action)


def get_service_logs(name: str, lines: int = 80) -> str:
    return get_manager().get_service_logs(name, lines)


# ═══════════════════════════════════════════════════════════════
#  服务依赖与详情 (systemd-only, graceful fallback for others)
# ═══════════════════════════════════════════════════════════════

def get_service_dependencies(name: str) -> Dict:
    """获取服务的依赖关系（systemd）。

    Returns:
        { requires, wanted_by, before, after, conflicts }
    """
    if ".." in name or "/" in name:
        return {"error": "Invalid service name"}

    mgr = get_manager()
    if not mgr.is_systemd():
        return {"error": "依赖分析仅支持 systemd", "service": name}

    result: Dict = {
        "service": name,
        "requires": [],
        "wanted_by": [],
        "before": [],
        "after": [],
        "conflicts": [],
    }

    fields = {
        "Requires": "requires",
        "WantedBy": "wanted_by",
        "Before": "before",
        "After": "after",
        "Conflicts": "conflicts",
    }

    out, _ = run_cmd(f"systemctl show {safe_quote(name)} --no-pager 2>/dev/null")
    for line in out.splitlines():
        for field, key in fields.items():
            if line.startswith(f"{field}="):
                val = line.split("=", 1)[1].strip()
                if val:
                    result[key] = sorted(val.split())
                break

    # Also get wants/requires via list-dependencies
    deps_out, _ = run_cmd(f"systemctl list-dependencies {safe_quote(name)} --no-pager --plain 2>/dev/null | head -50")
    result["dependency_tree"] = deps_out.strip()

    return result


def get_unit_file(name: str) -> Dict:
    """获取 systemd unit 文件内容。"""
    if ".." in name or "/" in name:
        return {"error": "Invalid service name"}

    mgr = get_manager()
    if not mgr.is_systemd():
        return {"error": "Unit 文件查看仅支持 systemd"}

    # Get the unit file path
    path_out, _ = run_cmd(f"systemctl show {safe_quote(name)} -p FragmentPath --no-pager 2>/dev/null")
    path = ""
    if path_out.startswith("FragmentPath="):
        path = path_out.split("=", 1)[1].strip()

    # Read unit file
    content = ""
    if path:
        out, code = run_cmd(f"sudo cat {safe_quote(path)} 2>/dev/null")
        if code == 0:
            content = out
        else:
            # Try systemctl cat
            out2, _ = run_cmd(f"systemctl cat {safe_quote(name)} 2>/dev/null")
            content = out2

    # Get drop-in files
    dropins_out, _ = run_cmd(f"systemctl show {safe_quote(name)} -p DropInPaths --no-pager 2>/dev/null")
    dropins = []
    if dropins_out.startswith("DropInPaths="):
        dp = dropins_out.split("=", 1)[1].strip()
        if dp:
            dropins = sorted(dp.split())

    return {
        "service": name,
        "unit_path": path,
        "content": content,
        "dropins": dropins,
    }


def get_service_status_detail(name: str) -> Dict:
    """获取服务详细状态（PID, 内存, CPU, 启动时间等）。"""
    if ".." in name or "/" in name:
        return {"error": "Invalid service name"}

    mgr = get_manager()
    if not mgr.is_systemd():
        # Basic fallback for non-systemd
        svcs = mgr.get_services()
        for s in svcs:
            if s["name"] == name:
                return {"service": name, "active": s["active"], "sub": s["sub"], "init": mgr.name}
        return {"error": "Service not found"}

    result: Dict = {"service": name, "init": "systemd"}

    # systemctl show for structured data
    props = {
        "ActiveState": "active",
        "SubState": "sub",
        "MainPID": "pid",
        "MemoryCurrent": "memory",
        "CPUUsageNSec": "cpu_ns",
        "ExecMainStartTimestamp": "started_at",
        "LoadState": "load",
        "UnitFileState": "enabled_status",
        "Description": "description",
    }

    out, _ = run_cmd(f"systemctl show {safe_quote(name)} --no-pager 2>/dev/null")
    for line in out.splitlines():
        for prop, key in props.items():
            if line.startswith(f"{prop}="):
                val = line.split("=", 1)[1].strip()
                if val:
                    # Parse numeric values
                    if key == "pid" and val.isdigit() and int(val) > 0:
                        result[key] = int(val)
                    elif key == "memory" and val.isdigit():
                        result[key] = int(val)
                    elif key == "cpu_ns" and val.isdigit():
                        result[key] = int(val)
                    else:
                        result[key] = val
                break

    # Get process info via ps for the main PID
    pid = result.get("pid")
    if pid and pid > 0:
        ps_out, _ = run_cmd(f"ps -p {pid} -o rss=,pcpu=,etime= --no-headers 2>/dev/null")
        if ps_out.strip():
            parts = ps_out.split()
            if len(parts) >= 3:
                try:
                    result["rss_kb"] = int(parts[0])
                    result["cpu_percent"] = float(parts[1])
                except (ValueError, IndexError):
                    pass
                result["elapsed"] = parts[-1].strip()

    # Get listen ports for this service
    if pid and pid > 0:
        ports_out, _ = run_cmd(f"sudo ss -tlnp 2>/dev/null | grep 'pid={pid}'")
        ports = []
        for line in ports_out.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                ports.append(parts[3])  # local address:port
        result["listen_ports"] = ports

    return result


def get_service_enablement() -> List[Dict]:
    """获取所有服务的启用状态（开机自启 vs 手动启动）。"""
    mgr = get_manager()
    if not mgr.is_systemd():
        svcs = mgr.get_services()
        return [{"name": s["name"], "enabled": s["active"] == "active", "init": mgr.name} for s in svcs]

    result = []
    out, _ = run_cmd("systemctl list-unit-files --type=service --no-pager --no-legend 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            result.append({
                "name": parts[0],
                "state": parts[1],  # enabled, disabled, static, masked, indirect
            })
    return result
