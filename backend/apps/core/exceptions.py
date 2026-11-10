import logging

from rest_framework.views import exception_handler

logger = logging.getLogger("asitech.api")


def api_exception_handler(exc, context):
    """Uniform error envelope: {"error": {"code", "message", "details"}}.

    Unhandled exceptions still propagate to Django (500, logged with traceback),
    so internals are never leaked to clients.
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    code = getattr(exc, "default_code", "error")
    data = response.data
    if isinstance(data, dict) and set(data) == {"detail"}:
        message, details = str(data["detail"]), None
        code = getattr(data["detail"], "code", code)
    else:
        message, details = "Invalid input.", data
        code = "invalid"
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
