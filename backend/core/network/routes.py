"""Routing table management."""
import json
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


def get_routes() -> List[Dict]:
    routes = []
    out, _ = run_cmd("ip -j route show 2>/dev/null")
    if out.strip():
        try:
            data = json.loads(out)
            for r in data:
                routes.append({
                    "dst": r.get("dst", "default"),
                    "gateway": r.get("gateway", ""),
                    "dev": r.get("dev", ""),
                    "proto": r.get("protocol", ""),
                    "metric": r.get("metric", ""),
                })
        except json.JSONDecodeError:
            pass
    return routes


def add_route(dst: str, gateway: str = "", dev: str = "", metric: str = "") -> Tuple[str, int]:
    cmd = f"sudo ip route add {safe_quote(dst)}"
    if gateway:
        cmd += f" via {safe_quote(gateway)}"
    if dev:
        cmd += f" dev {safe_quote(dev)}"
    if metric:
        cmd += f" metric {safe_quote(metric)}"
    return run_cmd(cmd + " 2>&1", timeout=10)


def delete_route(dst: str, gateway: str = "") -> Tuple[str, int]:
    cmd = f"sudo ip route del {safe_quote(dst)}"
    if gateway:
        cmd += f" via {safe_quote(gateway)}"
    return run_cmd(cmd + " 2>&1", timeout=10)
