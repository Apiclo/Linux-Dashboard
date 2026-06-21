"""GPU detection and environment queries."""
import os
import re
import tempfile
from typing import Dict, List, Tuple, Optional
from utils.helpers import run_cmd, safe_quote, safe_temp_file
from core.distro import detect_distro, detect_aur_helper
from ._common import NVIDIA_SMI_REALTIME_SCRIPT, INITRAMFS_CMDS
from .cuda import get_cuda_info

# PID of the running nvidia-smi realtime monitor (set by start_nvidia_monitor)
_monitor_pid: Optional[int] = None


def detect_gpus() -> List[Dict]:
    gpus: List[Dict] = []
    out, code = run_cmd("lspci -nn 2>/dev/null")
    if code != 0: return gpus
    for line in out.splitlines():
        low = line.lower()
        if "vga" in low or "3d" in low or "display" in low:
            gpu: Dict = {"raw": line}
            m = re.match(r'^([0-9a-fA-F:.]+)', line)
            if m: gpu["pci_id"] = m.group(1)
            id_m = re.search(r'\[([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\]', line)
            gpu["device_id"] = id_m.group(1) if id_m else ""
            if "nvidia" in low: gpu["vendor"] = "NVIDIA"; gpu["type"] = "nvidia"
            elif "amd" in low or "ati" in low: gpu["vendor"] = "AMD"; gpu["type"] = "amd"
            elif "intel" in low: gpu["vendor"] = "Intel"; gpu["type"] = "intel"
            else: gpu["vendor"] = "Unknown"; gpu["type"] = "unknown"
            gpu["name"] = re.sub(r'\s*\[[0-9a-fA-F:]+\]\s*$', '', line.split(":", 2)[-1].strip())
            gpus.append(gpu)
    return gpus


def get_nvidia_smi_info() -> List[Dict]:
    out, code = run_cmd("nvidia-smi --query-gpu=index,driver_version,name,temperature.gpu,memory.total,memory.used,utilization.gpu,pci.bus_id --format=csv,noheader,nounits 2>/dev/null")
    if code != 0 or not out: return []
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 7:
            gpus.append({"index": parts[0], "driver_version": parts[1], "gpu_name": parts[2], "temperature": parts[3], "vram_total": parts[4], "vram_used": parts[5], "utilization": parts[6], "pci_bus": parts[7] if len(parts) > 7 else ""})
    return gpus


def get_nvidia_driver_detail() -> Dict:
    info: Dict = {}
    ver, _ = run_cmd("cat /proc/driver/nvidia/version 2>/dev/null | head -2")
    if ver: info["proc_version"] = ver
    mod, _ = run_cmd("modinfo nvidia 2>/dev/null | grep -E '^(version|vermagic):'")
    for line in mod.splitlines():
        if "version:" in line and "vermagic" not in line: info["module_version"] = line.split(":", 1)[1].strip()
        elif "vermagic:" in line: info["vermagic"] = line.split(":", 1)[1].strip()
    return info


def check_nouveau() -> Dict:
    out, _ = run_cmd("lsmod | grep nouveau")
    loaded = bool(out.strip())
    bl, _ = run_cmd("cat /etc/modprobe.d/*nouveau* 2>/dev/null | grep -i blacklist")
    return {"loaded": loaded, "blacklisted": "blacklist" in bl.lower() if bl else False}


def blacklist_nouveau() -> Tuple[bool, str]:
    fd, tmp = tempfile.mkstemp(suffix=".conf", prefix="blacklist-nouveau-")
    try:
        os.write(fd, b"blacklist nouveau\noptions nouveau modeset=0\n")
        os.close(fd)
        _, code = run_cmd(f"sudo cp {safe_quote(tmp)} /etc/modprobe.d/blacklist-nouveau.conf")
        if code == 0: _update_initramfs(); return True, "nouveau 已加入黑名单，需要重启"
        return False, "写入失败"
    finally:
        try: os.remove(tmp)
        except OSError: pass


def check_secure_boot() -> Dict:
    mok, code = run_cmd("mokutil --sb-state 2>/dev/null")
    if code == 0 and "SecureBoot enabled" in mok: return {"enabled": True, "output": mok.strip()}
    out, _ = run_cmd("od -An -t x1 /sys/firmware/efi/efivars/SecureBoot-* 2>/dev/null | tail -1")
    if out:
        parts = out.strip().split()
        if len(parts) >= 5 and parts[4] == "01": return {"enabled": True, "output": "SecureBoot enabled"}
    return {"enabled": False, "output": mok.strip() if mok else "Not detected"}


def get_running_kernel() -> str:
    out, _ = run_cmd("uname -r")
    return out


def get_kernel_headers_path() -> str:
    kernel = get_running_kernel()
    for p in [f"/usr/src/linux-headers-{kernel}", f"/usr/src/kernels/{kernel}", f"/lib/modules/{kernel}/build"]:
        if os.path.exists(p): return p
    return ""


def get_display_manager() -> Optional[str]:
    for dm in ["sddm", "gdm", "gdm3", "lightdm", "lxdm"]:
        _, code = run_cmd(f"systemctl is-active {dm} 2>/dev/null")
        if code == 0: return dm
    return None


def get_loaded_modules() -> str:
    out, _ = run_cmd("lsmod | grep -E 'nvidia|nouveau|amdgpu|i915'")
    return out


def _update_initramfs():
    distro = detect_distro()
    pm = distro["pkg_manager"]
    cmd = INITRAMFS_CMDS.get(pm)
    if cmd: run_cmd(f"{cmd} 2>/dev/null")


def _update_initramfs_cmd(cmds: List[str]):
    distro = detect_distro()
    pm = distro["pkg_manager"]
    cmd = INITRAMFS_CMDS.get(pm)
    if cmd: cmds.append(f"{cmd} 2>/dev/null || true")


def get_detect_data():
    """Full GPU environment detection — single call for the detect endpoint."""
    nvidia = get_nvidia_smi_info()
    return {
        "gpus": detect_gpus(),
        "nvidia_info": nvidia[0] if nvidia else None,
        "nvidia_gpus": nvidia,
        "nvidia_detail": get_nvidia_driver_detail(),
        "nouveau": check_nouveau(),
        "display_manager": get_display_manager(),
        "kernel": get_running_kernel(),
        "kernel_headers": get_kernel_headers_path(),
        "cuda_info": get_cuda_info(),
        "secure_boot": check_secure_boot(),
        "distro": detect_distro(),
        "aur_helper": detect_aur_helper(),
        "loaded_modules": get_loaded_modules(),
    }


def get_distro_info():
    """Return distribution information (for the standalone distro endpoint)."""
    return detect_distro()


def get_nvidia_smi_realtime() -> str:
    """获取 nvidia-smi 实时信息（供 SSE 流轮询）。"""
    out, code = run_cmd("nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,fan.speed,clocks.gr,clocks.mem --format=csv,noheader 2>/dev/null", timeout=10)
    if code != 0:
        out2, _ = run_cmd("nvidia-smi 2>/dev/null | head -20")
        return out2
    return out.strip()


def start_nvidia_monitor() -> str:
    """启动 nvidia-smi 实时监控脚本并后台运行。返回 shell 命令字符串。

    监控进程 PID 存储在 _monitor_pid，可通过 stop_nvidia_monitor() 停止。
    """
    import subprocess

    global _monitor_pid

    # Stop any existing monitor first
    stop_nvidia_monitor()

    # Remove any stale stop file
    stop_file = "/tmp/.tuxtacklebox_nvidia_monitor_stop"
    if os.path.exists(stop_file):
        try:
            os.remove(stop_file)
        except OSError:
            pass

    tmp = safe_temp_file(suffix=".sh", content=NVIDIA_SMI_REALTIME_SCRIPT)

    cmd = f"bash {safe_quote(tmp)}"
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _monitor_pid = proc.pid
        return f"nvidia-smi realtime monitor started (PID: {_monitor_pid})"
    except Exception as e:
        return f"Failed to start monitor: {e}"


def stop_nvidia_monitor() -> str:
    """停止运行中的 nvidia-smi 实时监控进程。"""
    import subprocess

    global _monitor_pid

    stop_file = "/tmp/.tuxtacklebox_nvidia_monitor_stop"

    # Touch the stop file so the script's own loop see it
    try:
        with open(stop_file, "w") as f:
            f.write("stop\n")
    except OSError:
        pass

    # Kill by tracked PID first
    if _monitor_pid is not None:
        try:
            os.kill(_monitor_pid, 15)  # SIGTERM
        except OSError:
            pass
        _monitor_pid = None

    # Clean up any leftover processes by matching the command pattern
    try:
        subprocess.run(
            ["pkill", "-f", "nvidia-smi realtime monitor"],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass

    # Remove stop file
    try:
        os.remove(stop_file)
    except OSError:
        pass

    return "nvidia-smi realtime monitor stopped"
