def client_ip(request) -> str | None:
    """Client IP as seen by Django.

    REMOTE_ADDR is used on purpose. Behind a reverse proxy, the proxy must be
    configured to pass the real client address (e.g. uvicorn --proxy-headers
    with --forwarded-allow-ips limited to the proxy). Trusting
    X-Forwarded-For from arbitrary clients would allow spoofing audit logs.
    """
    return request.META.get("REMOTE_ADDR") or None


def user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:300]
