"""Async task manager."""
import subprocess
import threading
import queue
import time
import logging
from typing import Dict, Optional

log = logging.getLogger("tasks")

OUTPUT_QUEUES: Dict[str, queue.Queue] = {}
_RUNNING_PROCESSES: Dict[str, subprocess.Popen] = {}
_TASK_COUNTER = 0
_TASK_LOCK = threading.Lock()
_MAX_TASKS = 50
_MAX_QUEUE_SIZE = 5000
_MAX_TASK_AGE = 3600


def next_task_id(prefix: str = "task") -> str:
    global _TASK_COUNTER
    with _TASK_LOCK:
        if len(OUTPUT_QUEUES) >= _MAX_TASKS:
            cleanup_queues()
            if len(OUTPUT_QUEUES) >= _MAX_TASKS:
                raise RuntimeError("Too many active tasks")
        _TASK_COUNTER += 1
        return f"{prefix}_{_TASK_COUNTER}_{int(time.time())}"


def get_queue(task_id: str) -> queue.Queue:
    if task_id not in OUTPUT_QUEUES:
        OUTPUT_QUEUES[task_id] = queue.Queue(maxsize=_MAX_QUEUE_SIZE)
    return OUTPUT_QUEUES[task_id]


def run_async(task_id: str, cmd: str) -> None:
    q = get_queue(task_id)
    proc = None
    try:
        log.info(f"Task {task_id}: {cmd[:120]}...")
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        _RUNNING_PROCESSES[task_id] = proc
        for line in proc.stdout:
            try:
                q.put(("output", line.rstrip("\n")), timeout=1)
            except queue.Full:
                pass
        proc.wait()
        q.put(("done", proc.returncode))
        log.info(f"Task {task_id} done: exit={proc.returncode}")
    except Exception as e:
        log.error(f"Task {task_id} error: {e}")
        q.put(("error", str(e)))
        q.put(("done", -1))
    finally:
        _RUNNING_PROCESSES.pop(task_id, None)
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def start_task(cmd: str, prefix: str = "task") -> str:
    task_id = next_task_id(prefix)
    threading.Thread(target=run_async, args=(task_id, cmd), daemon=True).start()
    return task_id


def cancel_task(task_id: str) -> bool:
    proc = _RUNNING_PROCESSES.get(task_id)
    if proc and proc.poll() is None:
        try:
            proc.kill()
            q = get_queue(task_id)
            q.put(("error", "Task cancelled"))
            q.put(("done", -1))
            return True
        except OSError:
            pass
    return False


def cleanup_queues() -> int:
    now = time.time()
    cleaned = 0
    for tid in list(OUTPUT_QUEUES.keys()):
        try:
            ts = int(tid.split("_")[-1])
            if now - ts > _MAX_TASK_AGE:
                del OUTPUT_QUEUES[tid]
                cleaned += 1
        except (ValueError, IndexError):
            pass
    for tid, proc in list(_RUNNING_PROCESSES.items()):
        if proc.poll() is not None:
            _RUNNING_PROCESSES.pop(tid, None)
    return cleaned


def start_cleanup_thread():
    def _loop():
        while True:
            time.sleep(300)
            try:
                cleanup_queues()
            except Exception:
                pass
    threading.Thread(target=_loop, daemon=True).start()
