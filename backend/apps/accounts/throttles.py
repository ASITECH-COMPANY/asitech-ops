from rest_framework.throttling import SimpleRateThrottle

from .models import normalize_email


class LoginEmailRateThrottle(SimpleRateThrottle):
    """Limits attempts per target account, independent of the client IP.

    Complements the per-IP "login" scope against distributed guessing.
    """

    scope = "login_email"

    def get_cache_key(self, request, view):
        email = normalize_email(str(request.data.get("email", ""))) if hasattr(request, "data") else ""
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}
