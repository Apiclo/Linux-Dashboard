"""Shared internals for GPU package."""
import re
import time
from typing import Dict, Tuple

OFFLINE_PKG_DIR = "/opt/linux-toolbox/nvidia-offline"
OFFLINE_GENERATE_DIR = "/opt/linux-toolbox/nvidia-generated"
_version_cache: Dict[str, Tuple[float, any]] = {}
_PKG_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._+\-:~]*$')
_CUDA_FALLBACK_VERSIONS = ["12.8", "12.6", "12.4", "12.2", "11.8"]


def _cached(key: str, fetcher, ttl=300):
    now = time.time()
    if key in _version_cache:
        ts, val = _version_cache[key]
        if now - ts < ttl: return val
    val = fetcher()
    _version_cache[key] = (now, val)
    return val


NVIDIA_SMI_REALTIME_SCRIPT = """#!/bin/bash
# nvidia-smi realtime monitor
STOP_FILE="/tmp/.tuxtacklebox_nvidia_monitor_stop"
trap 'rm -f "$STOP_FILE"' EXIT
while true; do
  [ -f "$STOP_FILE" ] && break
  nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,fan.speed --format=csv,noheader 2>/dev/null
  sleep 2
done
"""

INITRAMFS_CMDS = {
    'apt': 'sudo update-initramfs -u',
    'pacman': 'sudo mkinitcpio -P',
    'dnf': 'sudo dracut --force',
    'yum': 'sudo dracut --force',
    'zypper': 'sudo dracut --force',
}
