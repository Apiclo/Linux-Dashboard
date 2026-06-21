"""PAM-based authentication."""
import os
import pamela
import secrets
import logging
from typing import Optional, Tuple
from functools import wraps
from flask import request, jsonify, session

log = logging.getLogger("auth")
_pam_service = "login"


def authenticate(username: str, password: str) -> Tuple[bool, str]:
    if not username or not password:
        return False, "用户名和密码不能为空"
    try:
        pamela.authenticate(username, password, service=_pam_service)
        log.info(f"PAM auth success: {username}")
        return True, "登录成功"
    except pamela.PAMError as e:
        log.warning(f"PAM auth failed: {username} ({e})")
        return False, f"认证失败: {e}"


def init_session_secret(app):
    app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("authenticated"):
            return f(*args, **kwargs)
        return jsonify({"success": False, "message": "未登录", "code": 401}), 401
    return wrapper


def get_current_user() -> Optional[str]:
    return session.get("username")
