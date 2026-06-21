"""User management: list, add, delete, change password."""
import re
from typing import Dict, List
from utils.helpers import run_cmd, safe_quote


def get_users() -> List[Dict]:
    """List system users with login shells."""
    users = []
    try:
        with open("/etc/passwd") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 7:
                    shell = parts[6]
                    if shell and shell not in ("/usr/sbin/nologin", "/bin/false", "/sbin/nologin"):
                        users.append({"username": parts[0], "uid": int(parts[2]), "gid": int(parts[3]), "home": parts[5], "shell": shell})
    except Exception:
        pass
    return users


def add_user(username: str, password: str, groups: str = "", shell: str = "/bin/bash") -> Dict:
    """Add a new system user."""
    import subprocess
    if not re.match(r'^[a-z_][a-z0-9_-]*$', username):
        return {"success": False, "message": "Invalid username"}
    if not password or len(password) > 128:
        return {"success": False, "message": "Invalid password"}
    # Create user
    cmd = ["sudo", "useradd", "-m", "-s", shell, username]
    if groups:
        cmd = ["sudo", "useradd", "-m", "-s", shell, "-G", groups, username]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        return {"success": False, "message": f"Failed to create user: {proc.stderr.strip()}"}
    # Set password via stdin (no shell interpolation)
    proc = subprocess.run(
        ["sudo", "chpasswd"],
        input=f"{username}:{password}",
        capture_output=True, text=True, timeout=15
    )
    if proc.returncode != 0:
        return {"success": True, "message": f"User {username} created but password set failed: {proc.stderr.strip()}"}
    return {"success": True, "message": f"User {username} created"}


def delete_user(username: str) -> Dict:
    """Delete a system user."""
    if username in ("root",):
        return {"success": False, "message": "Cannot delete root"}
    out, code = run_cmd(f"sudo userdel -r {safe_quote(username)}")
    return {"success": code == 0, "message": out or f"User {username} deleted"}


def change_password(username: str, password: str) -> Dict:
    """Change user password."""
    import subprocess
    if not username or not password:
        return {"success": False, "message": "Username and password required"}
    if len(password) > 128:
        return {"success": False, "message": "Password too long"}
    proc = subprocess.run(
        ["sudo", "chpasswd"],
        input=f"{username}:{password}",
        capture_output=True, text=True, timeout=15
    )
    return {"success": proc.returncode == 0, "message": proc.stderr.strip() if proc.returncode != 0 else f"Password changed for {username}"}
