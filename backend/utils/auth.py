"""PAM-based authentication."""
import os
import pamela
import secrets
import logging
from typing import Optional, Tuple
from flask import request, session

log = logging.getLogger("auth")

# PAM 服务优先级：su 最可靠，login 次之，passwd 最宽松
_PAM_SERVICES = ["su", "login", "passwd"]


def authenticate(username: str, password: str) -> Tuple[bool, str]:
    if not username or not password:
        return False, "用户名和密码不能为空"

    errors = []
    for svc in _PAM_SERVICES:
        try:
            pamela.authenticate(username, password, service=svc)
            log.info(f"PAM auth success via {svc}: {username}")
            return True, "登录成功"
        except pamela.PAMError as e:
            errors.append(f"{svc}: {e}")
        except Exception as e:
            errors.append(f"{svc}: {e}")

    # 所有服务都失败，给出明确错误
    log.warning(f"PAM auth failed for {username}: {'; '.join(errors)}")
    # 检查常见问题
    hints = []
    if os.geteuid() != 0:
        hints.append("后端未以 root 运行，无法读取 /etc/shadow")
    if username == "root":
        hints.append("某些发行版禁止 root 通过 PAM login 登录，尝试用普通用户或检查 /etc/pam.d/su")
    hint_str = ("（" + "；".join(hints) + "）") if hints else ""
    return False, f"认证失败{hint_str}"


def init_session_secret(app):
    app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))


def get_current_user() -> Optional[str]:
    return session.get("username")
