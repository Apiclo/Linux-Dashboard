"""Backward-compatible re-export shim.

All functionality has been moved to:
  - utils.shell      — run_cmd, safe_quote
  - utils.validators — ALLOWED_CONFIG_PATHS, BLOCKED_CONFIG_PATHS,
                       validate_hostname, validate_path, safe_temp_file,
                       validate_package_name, validate_ip, validate_device_path,
                       ALLOWED_FW_COMMANDS, validate_fw_command
  - utils.decorators — safe_api, validate_json, require_auth

Existing code using ``from utils.helpers import ...`` continues to work.
New code should import from the specific submodules.
"""
# shell
from utils.shell import atomic_sudo_write, run_cmd, safe_quote

# validators
from utils.validators import (
    ALLOWED_CONFIG_PATHS,
    BLOCKED_CONFIG_PATHS,
    validate_hostname,
    validate_path,
    validate_package_name,
    validate_ip,
    validate_device_path,
    ALLOWED_FW_COMMANDS,
    validate_fw_command,
)

# decorators
from utils.decorators import safe_api, validate_json, require_auth

# local (remains here — small and tightly coupled to helpers)
import os
import tempfile


def safe_temp_file(suffix: str = "", prefix: str = "lt_", content: str = "") -> str:
    """Create a temporary file with optional initial content. Returns the path."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    try:
        if content:
            os.write(fd, content.encode())
    finally:
        os.close(fd)
    return path
