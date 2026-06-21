"""Shell command execution, quoting, and atomic file write utilities."""
import fcntl
import os
import subprocess
import shlex
import tempfile
from typing import Tuple, Optional


def run_cmd(cmd: str, timeout: int = 30) -> Tuple[str, int]:
    """Execute a shell command and return (stdout, returncode)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", -1
    except Exception as e:
        return str(e), -1


def safe_quote(value: str) -> str:
    """Shell-escape a value with shlex.quote."""
    return shlex.quote(value.strip())


def atomic_sudo_write(path: str, content: str, mode: int = 0o644,
                      post_cmd: Optional[str] = None) -> Tuple[bool, str]:
    """Write content to a system file atomically via sudo.

    Creates a temp file with the provided content, then uses ``sudo cp``
    to move it into place.  An advisory flock is held on a per-path lock
    file to serialise concurrent writes to the same destination.

    Args:
        path: Absolute target path (e.g. ``/etc/hosts``).
        content: The full file content to write.
        mode: Unix permission bits applied to the temp file (default 0o644).
        post_cmd: Optional shell command to run after the copy succeeds
                  (e.g. ``'sudo systemctl restart sshd'``).

    Returns:
        (success, message) tuple.
    """
    if not path.startswith("/"):
        return False, f"Path must be absolute: {path}"

    # Per-path lock file to serialise concurrent writes
    lock_path = f"/tmp/.tuxtacklebox_lock_{path.replace('/', '_')}"
    fd_lock = -1
    fd_tmp = -1
    tmp_path = None

    try:
        fd_tmp, tmp_path = tempfile.mkstemp(suffix=".atomic")
        os.write(fd_tmp, content.encode("utf-8"))
        os.close(fd_tmp)
        fd_tmp = -1
        os.chmod(tmp_path, mode)

        fd_lock = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd_lock, fcntl.LOCK_EX)

        out, code = run_cmd(
            f"sudo cp {safe_quote(tmp_path)} {safe_quote(path)} 2>&1",
            timeout=15
        )
        if code != 0:
            return False, f"Failed to write {path}: {out}"

        if post_cmd:
            out2, code2 = run_cmd(post_cmd, timeout=30)
            if code2 != 0:
                return False, f"File written but post-cmd failed: {out2}"
            out = out2

        return True, out.strip() if out else "written"

    except Exception as e:
        return False, str(e)

    finally:
        if fd_lock >= 0:
            try:
                fcntl.flock(fd_lock, fcntl.LOCK_UN)
                os.close(fd_lock)
                os.remove(lock_path)
            except OSError:
                pass
        if fd_tmp >= 0:
            try:
                os.close(fd_tmp)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
