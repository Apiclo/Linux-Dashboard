"""Flask route decorators: safe_api, validate_json, require_auth."""
import logging
from functools import wraps
from typing import Optional, List
from flask import request, jsonify, session

from utils.errors import AppError, AuthError, ValidationError

log = logging.getLogger("decorators")


def safe_api(f):
    """Decorator that catches all exceptions and returns structured JSON.

    AppError subclasses are converted to appropriate HTTP status codes.
    Unexpected exceptions are logged and returned as 500 INTERNAL_ERROR.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            # If the route returned a Flask Response directly, pass it through
            return result
        except AppError as e:
            log.warning(f"AppError in {f.__name__}: [{e.code}] {e.message}")
            return jsonify(e.to_dict()), e.status
        except Exception as e:
            log.error(f"API error in {f.__name__}: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
            }), 500
    return wrapper


def validate_json(required_fields: Optional[List[str]] = None):
    """Decorator factory: validates JSON body and required fields.

    Raises ValidationError for missing / malformed input so the route
    never has to check for those conditions itself.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if data is None:
                raise ValidationError("Request body must be JSON")
            if required_fields:
                missing = [k for k in required_fields if k not in data]
                if missing:
                    raise ValidationError(f"Missing: {', '.join(missing)}")
            return f(data, *args, **kwargs)
        return wrapper
    return decorator


def require_auth(f):
    """Decorator: require authenticated session (raises AuthError on failure)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("authenticated"):
            return f(*args, **kwargs)
        raise AuthError("未登录")
    return wrapper
