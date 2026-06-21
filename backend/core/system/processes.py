"""Process management: list, search, kill, renice, tree view."""
import re
import os
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def list_processes(sort_by: str = "cpu", filter_name: str = "", limit: int = 100) -> List[Dict]:
    """列出进程，按 CPU/内存排序。

    Args:
        sort_by: cpu | mem | pid
        filter_name: 进程名过滤（可选）。
        limit: 最大返回数量。
    """
    sort_map = {"cpu": "-pcpu", "mem": "-pmem", "pid": "-pid"}
    sort_opt = sort_map.get(sort_by, "-pcpu")
    limit = max(1, min(limit, 500))

    cmd = f"ps aux --sort={sort_opt} --no-headers 2>/dev/null"
    if filter_name:
        cmd += f" | grep -i {safe_quote(filter_name)} | grep -v grep"
    cmd += f" | head -n {limit}"

    out, _ = run_cmd(cmd)
    processes = []
    for line in out.splitlines():
        parts = line.split(None, 10)  # ps aux has 11 columns
        if len(parts) >= 11:
            try:
                processes.append({
                    "user": parts[0],
                    "pid": int(parts[1]),
                    "cpu": float(parts[2]),
                    "mem": float(parts[3]),
                    "vsz": int(parts[4]) if parts[4].isdigit() else parts[4],
                    "rss": int(parts[5]) if parts[5].isdigit() else parts[5],
                    "tty": parts[6],
                    "stat": parts[7],
                    "start": parts[8],
                    "time": parts[9],
                    "command": parts[10][:200],  # Truncate long commands
                })
            except (ValueError, IndexError):
                pass
    return processes


def get_process_tree() -> Dict:
    """获取进程树（pstree 格式）。"""
    out, _ = run_cmd("ps -eo pid,ppid,user,comm --forest --no-headers 2>/dev/null | head -200")
    # Build tree structure
    processes: Dict[int, Dict] = {}
    roots = []

    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) >= 4:
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
                node = {
                    "pid": pid,
                    "ppid": ppid,
                    "user": parts[2],
                    "name": parts[3],
                    "children": [],
                }
                processes[pid] = node
            except ValueError:
                pass

    # Link children
    orphan_roots = []
    for pid, node in processes.items():
        ppid = node["ppid"]
        if ppid in processes and ppid != pid:
            processes[ppid]["children"].append(node)
        elif ppid == 0 or ppid == 1 or ppid == 2 or ppid not in processes:
            roots.append(node)
        else:
            orphan_roots.append(node)

    return {"roots": roots[:50], "total": len(processes)}


def get_process_detail(pid: int) -> Dict:
    """获取进程详细信息。"""
    if pid <= 0 or pid > 4194304:
        return {"error": "Invalid PID"}

    result: Dict = {"pid": pid}

    # Basic info via ps
    ps_out, _ = run_cmd(f"ps -p {pid} -o pid,ppid,user,pcpu,pmem,vsz,rss,stat,etime,time,comm,args --no-headers 2>/dev/null")
    if not ps_out.strip():
        return {"error": f"Process {pid} not found"}

    parts = ps_out.split(None, 11)
    if len(parts) >= 12:
        result.update({
            "ppid": int(parts[1]) if parts[1].isdigit() else parts[1],
            "user": parts[2],
            "cpu": float(parts[3]) if parts[3].replace('.', '').isdigit() else parts[3],
            "mem": float(parts[4]) if parts[4].replace('.', '').isdigit() else parts[4],
            "vsz": parts[5],
            "rss": parts[6],
            "stat": parts[7],
            "elapsed": parts[8],
            "cpu_time": parts[9],
            "comm": parts[10],
            "cmdline": parts[11][:500],
        })

    # Open files count
    fd_out, _ = run_cmd(f"sudo ls /proc/{pid}/fd 2>/dev/null | wc -l")
    result["open_fds"] = int(fd_out.strip()) if fd_out.strip().isdigit() else 0

    # cgroup
    try:
        with open(f"/proc/{pid}/cgroup") as f:
            result["cgroup"] = f.read().strip()[:500]
    except Exception:
        result["cgroup"] = ""

    # Environment (truncated)
    try:
        with open(f"/proc/{pid}/environ") as f:
            env = f.read().replace('\x00', '\n')[:2000]
            result["environ"] = env
    except Exception:
        result["environ"] = ""

    # Memory maps summary
    maps_out, _ = run_cmd(f"cat /proc/{pid}/smaps_rollup 2>/dev/null | head -10")
    result["memory_summary"] = maps_out.strip()[:1000]

    return result


def kill_process(pid: int, signal: str = "SIGTERM") -> Tuple[bool, str]:
    """终止进程。

    Args:
        pid: 进程 PID。
        signal: 信号 (SIGTERM, SIGKILL, SIGINT, SIGHUP, SIGSTOP, SIGCONT)。
    """
    if pid <= 0 or pid > 4194304:
        return False, f"Invalid PID: {pid}"

    allowed_signals = {"SIGTERM", "SIGKILL", "SIGINT", "SIGHUP", "SIGSTOP", "SIGCONT"}
    if signal not in allowed_signals:
        return False, f"Invalid signal: {signal}"

    # Safety: refuse to kill PID 1 (init), kernel threads (PID 2), or self
    if pid in (1, 2):
        return False, f"拒绝终止系统关键进程 PID {pid}"

    out, code = run_cmd(f"sudo kill -{signal} {pid} 2>&1", timeout=10)
    return code == 0, out.strip() or f"Sent {signal} to PID {pid}"


def renice_process(pid: int, nice_value: int) -> Tuple[bool, str]:
    """调整进程优先级。

    Args:
        pid: 进程 PID。
        nice_value: -20 (最高) 到 19 (最低)。
    """
    if pid <= 0 or pid > 4194304:
        return False, f"Invalid PID: {pid}"
    if not (-20 <= nice_value <= 19):
        return False, f"Nice 值必须在 -20 到 19 之间，当前: {nice_value}"

    out, code = run_cmd(f"sudo renice {nice_value} -p {pid} 2>&1", timeout=10)
    return code == 0, out.strip()


def get_system_load() -> Dict:
    """获取系统负载信息。"""
    result: Dict = {"load_avg": [], "procs_running": 0, "procs_blocked": 0, "procs_total": 0}

    # Load average
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            if len(parts) >= 3:
                result["load_avg"] = [float(parts[0]), float(parts[1]), float(parts[2])]
            if len(parts) >= 5:
                running_blocked = parts[3].split("/")
                result["procs_running"] = int(running_blocked[0])
                result["procs_total"] = int(running_blocked[1]) if len(running_blocked) > 1 else 0
                result["last_pid"] = int(parts[4])
    except Exception:
        pass

    return result


def get_top_processes(limit: int = 10) -> Dict:
    """获取 CPU 和内存占用最高的进程。"""
    cpu_out, _ = run_cmd(f"ps aux --sort=-pcpu --no-headers 2>/dev/null | head -{limit}")
    mem_out, _ = run_cmd(f"ps aux --sort=-pmem --no-headers 2>/dev/null | head -{limit}")

    def _parse(lines: str) -> List[Dict]:
        procs = []
        for line in lines.splitlines():
            parts = line.split(None, 10)
            if len(parts) >= 11:
                try:
                    procs.append({
                        "pid": int(parts[1]),
                        "user": parts[0],
                        "cpu": float(parts[2]),
                        "mem": float(parts[3]),
                        "command": parts[10][:100],
                    })
                except ValueError:
                    pass
        return procs

    return {"top_cpu": _parse(cpu_out), "top_mem": _parse(mem_out)}
