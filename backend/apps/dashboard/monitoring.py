"""Monitoring overview: per-server health summary and alerts derived from real data.

Alerts are computed on read from the latest agent reports; nothing is stored.
The dashboard localizes them from ``kind`` and ``params``.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.applications.models import Deployment
from apps.servers.models import MetricSample, Server, ServerInventory

WARN_PERCENT = 90
CRITICAL_PERCENT = 95


def _percent(used, total):
    return round(used / total * 100, 1) if used is not None and total else None


def overview(organization) -> dict:
    latest = MetricSample.objects.filter(server=OuterRef("pk")).order_by("-ts")
    servers = (
        Server.objects.filter(organization=organization)
        .annotate(
            m_ts=Subquery(latest.values("ts")[:1]),
            m_cpu=Subquery(latest.values("cpu_percent")[:1]),
            m_mem_used=Subquery(latest.values("memory_used")[:1]),
            m_mem_total=Subquery(latest.values("memory_total")[:1]),
            m_disk_used=Subquery(latest.values("disk_used")[:1]),
            m_disk_total=Subquery(latest.values("disk_total")[:1]),
        )
        .order_by("name")
    )
    inventories = {
        inv.server_id: inv for inv in ServerInventory.objects.filter(server__organization=organization)
    }
    alerts: list[dict] = []
    summaries: list[dict] = []
    stale_metrics = timezone.now() - timedelta(minutes=10)

    for server in servers:
        ref = {"id": str(server.pk), "name": server.name}
        memory = _percent(server.m_mem_used, server.m_mem_total)
        disk = _percent(server.m_disk_used, server.m_disk_total)
        fresh = server.m_ts is not None and server.m_ts >= stale_metrics
        inventory = inventories.get(server.pk)
        containers = (inventory.data.get("containers") or []) if inventory else []
        running = sum(1 for c in containers if c.get("state") == "running")
        summaries.append(
            {
                "server": ref,
                "status": server.status,
                "last_seen_at": server.last_seen_at,
                "cpu_percent": server.m_cpu if fresh else None,
                "memory_percent": memory if fresh else None,
                "disk_percent": disk if fresh else None,
                "containers_running": running if inventory else None,
                "containers_total": len(containers) if inventory else None,
                "docker": inventory.data.get("docker") if inventory else None,
            }
        )

        if server.status == Server.Status.OFFLINE:
            alerts.append(
                {
                    "severity": "critical",
                    "kind": "server_offline",
                    "server": ref,
                    "params": {"since": server.last_seen_at},
                }
            )
            continue
        if server.status != Server.Status.ONLINE:
            continue
        for kind, value in (("disk_high", disk), ("memory_high", memory)):
            if fresh and value is not None and value >= WARN_PERCENT:
                alerts.append(
                    {
                        "severity": "critical" if value >= CRITICAL_PERCENT else "warning",
                        "kind": kind,
                        "server": ref,
                        "params": {"percent": value},
                    }
                )
        if inventory and inventory.data.get("docker") == "unavailable":
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "docker_unavailable",
                    "server": ref,
                    "params": {"error": inventory.data.get("error", "")},
                }
            )
        for container in containers:
            managed = bool(container.get("app_id"))
            state = container.get("state")
            if state == "restarting" or (managed and state in ("exited", "dead")):
                alerts.append(
                    {
                        "severity": "warning",
                        "kind": "container_down",
                        "server": ref,
                        "params": {"container": container.get("name", ""), "state": state},
                    }
                )

    # Failed deployments of the last 24 h that were not followed by a success.
    since = timezone.now() - timedelta(hours=24)
    last_by_app: dict = {}
    for deployment in (
        Deployment.objects.filter(application__organization=organization, created_at__gte=since)
        .select_related("application")
        .order_by("application_id", "-created_at")
    ):
        last_by_app.setdefault(deployment.application_id, deployment)
    for deployment in last_by_app.values():
        if deployment.status == Deployment.Status.FAILED:
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "deployment_failed",
                    "application": {
                        "id": str(deployment.application_id),
                        "name": deployment.application.name,
                    },
                    "params": {"deployment_id": str(deployment.pk), "number": deployment.number},
                }
            )

    order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda a: order[a["severity"]])
    return {"generated_at": timezone.now(), "alerts": alerts, "servers": summaries}
