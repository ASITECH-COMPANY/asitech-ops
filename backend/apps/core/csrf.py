from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import SAFE_METHODS


class CSRFEnforcedMixin:
    """Enforce CSRF on unsafe methods even for anonymous requests.

    DRF only checks CSRF for session-authenticated users. Endpoints that can be
    called anonymously and then open a session (login, invitation acceptance)
    must also be protected, otherwise they allow login-CSRF attacks.
    """

    def initial(self, request, *args, **kwargs):
        if request.method not in SAFE_METHODS:
            SessionAuthentication().enforce_csrf(request)
        super().initial(request, *args, **kwargs)
