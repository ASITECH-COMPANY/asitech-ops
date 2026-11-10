from celery import shared_task

from . import services


@shared_task
def fail_stale_deployments() -> int:
    return services.fail_stale_deployments()
