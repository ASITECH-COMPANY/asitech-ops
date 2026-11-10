from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny, IsAuthenticated

_docs_permissions = [AllowAny] if (settings.API_DOCS_PUBLIC or settings.DEBUG) else [IsAuthenticated]

api_v1 = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.organizations.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.dashboard.urls")),
    path("", include("apps.servers.urls")),
]

urlpatterns = [
    path("api/v1/", include(api_v1)),
    path("api/agent/v1/", include("apps.servers.agent_urls")),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=_docs_permissions), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=_docs_permissions),
        name="api-docs",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema", permission_classes=_docs_permissions),
        name="api-redoc",
    ),
    path("admin/", admin.site.urls),
]
