import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from . import services
from .models import EnrollmentToken, MetricSample

logger = logging.getLogger("asitech.servers")


@shared_task
def mark_stale_servers_offline() -> int:
    return services.mark_stale_servers_offline()


@shared_task
def purge_old_metrics() -> int:
    cutoff = timezone.now() - timedelta(days=settings.METRICS_RETENTION_DAYS)
    deleted = MetricSample.objects.filter(ts__lt=cutoff).delete()[0]
    # Expired or used enrollment tokens are useless after a day.
    EnrollmentToken.objects.filter(expires_at__lt=timezone.now() - timedelta(days=1)).delete()
    if deleted:
        logger.info("Purged old metric samples", extra={"count": deleted})
    return deleted
