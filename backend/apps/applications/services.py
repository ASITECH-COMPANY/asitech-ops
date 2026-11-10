"""Applications, environment variables and deployments.

A deployment is executed by the agent of the application's server: the
Control Plane only prepares and signs the task, then records the logs and the
status the agent reports back.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.actions import AuditAction
from apps.audit.services import notify_organization, record
from apps.core import crypto
from apps.core.exceptions_api import Conflict
from apps.servers import dispatch
from apps.servers.models import Server

from .models import Application, Deployment, DeploymentLog, EnvironmentVariable

logger = logging.getLogger("asitech.deployments")

DEPLOY_EVENT = "deployment.status"
MAX_LOG_LINE = 4000


def _notify(app: Application) -> None:
    organization_id = app.organization_id
    transaction.on_commit(lambda: notify_organization(organization_id, DEPLOY_EVENT, "deployments"))


# --- Applications ------------------------------------------------------------------------------


@transaction.atomic
def create_application(organization, *, data: dict, actor, request=None) -> Application:
    token = data.pop("repo_token", "") or ""
    app = Application(organization=organization, created_by=actor, **data)
    if token:
        app.repo_token_encrypted = crypto.encrypt(token)
    try:
        with transaction.atomic():
            app.save()
    except IntegrityError as exc:
        raise _integrity_error(exc) from exc
    record(
        AuditAction.APPLICATION_CREATED,
        request=request,
        organization=organization,
        target=app,
        metadata={"repo_url": app.repo_url, "branch": app.branch, "server": app.server.name},
    )
    return app


def _integrity_error(exc: IntegrityError) -> ValidationError:
    message = str(exc)
    if "uniq_host_port_per_server" in message:
        return ValidationError(
            {"host_port": ["This port is already used by another application on this server."]}
        )
    return ValidationError({"slug": ["An application with this identifier already exists."]})


@transaction.atomic
def update_application(app: Application, *, changes: dict, request=None) -> Application:
    token = changes.pop("repo_token", None)
    diff = {k: {"from": getattr(app, k), "to": v} for k, v in changes.items() if getattr(app, k) != v}
    for key, change in diff.items():
        setattr(app, key, change["to"])
    if token is not None:
        app.repo_token_encrypted = crypto.encrypt(token) if token else ""
        diff["repo_token"] = {"from": "***", "to": "***" if token else ""}
    if not diff:
        return app
    if "server" in diff:
        raise ValidationError({"server": ["An application cannot be moved to another server yet."]})
    if "slug" in diff:
        # Container and image names on the server are derived from the identifier.
        raise ValidationError({"slug": ["The identifier cannot be changed after creation."]})
    try:
        with transaction.atomic():
            app.save()
    except IntegrityError as exc:
        raise _integrity_error(exc) from exc
    metadata = {k: v for k, v in diff.items() if k != "repo_token_encrypted"}
    for change in metadata.values():
        for side in ("from", "to"):
            if isinstance(change[side], Server):
                change[side] = change[side].name
    record(
        AuditAction.APPLICATION_UPDATED,
        request=request,
        organization=app.organization,
        target=app,
        metadata=metadata,
    )
    return app


@transaction.atomic
def delete_application(app: Application, *, request=None) -> bool:
    """Delete the application and ask the agent to remove its containers. Returns True if sent."""
    if app.deployments.filter(status__in=Deployment.ACTIVE_STATUSES).exists():
        raise Conflict("A deployment is in progress. Wait for it to finish.")
    sent = False
    if app.server.status == Server.Status.ONLINE:
        message = dispatch.build_task(
            task_id=str(app.pk),
            server_id=str(app.server_id),
            kind="deploy",
            payload={"action": "remove", "app": {"id": str(app.pk), "slug": app.slug}},
            timeout_seconds=300,
        )
        server_id = app.server_id
        transaction.on_commit(lambda: dispatch.send(server_id, message))
        sent = True
    record(
        AuditAction.APPLICATION_DELETED,
        request=request,
        organization=app.organization,
        target=app,
        metadata={"server": app.server.name, "containers_removed": sent},
    )
    app.delete()
    return sent


@transaction.atomic
def set_environment(app: Application, *, items: list[dict], request=None) -> None:
    """Replace the variable set. A secret sent without a value keeps its stored value."""
    existing = {var.key: var for var in app.env_vars.all()}
    keys = [item["key"] for item in items]
    if len(keys) != len(set(keys)):
        raise ValidationError({"variables": ["Each key must appear only once."]})
    added, changed = [], []
    for item in items:
        var = existing.pop(item["key"], None)
        value = item.get("value")
        if var is None:
            if value is None:
                raise ValidationError({"variables": [f"{item['key']}: a value is required."]})
            EnvironmentVariable.objects.create(
                application=app,
                key=item["key"],
                value_encrypted=crypto.encrypt(value),
                is_secret=item["is_secret"],
            )
            added.append(item["key"])
            continue
        updates = []
        if value is not None and crypto.decrypt(var.value_encrypted) != value:
            var.value_encrypted = crypto.encrypt(value)
            updates.append("value_encrypted")
        if var.is_secret != item["is_secret"]:
            var.is_secret = item["is_secret"]
            updates.append("is_secret")
        if updates:
            var.save(update_fields=[*updates, "updated_at"])
            changed.append(item["key"])
    removed = sorted(existing)
    EnvironmentVariable.objects.filter(pk__in=[v.pk for v in existing.values()]).delete()
    if added or changed or removed:
        # Names only: values never reach the audit log.
        record(
            AuditAction.APPLICATION_ENV_UPDATED,
            request=request,
            organization=app.organization,
            target=app,
            metadata={"added": added, "changed": changed, "removed": removed},
        )


# --- Deployments --------------------------------------------------------------------------------


def _payload(app: Application, deployment: Deployment, *, image: str | None) -> dict:
    env, secret_keys = {}, []
    for var in app.env_vars.all():
        env[var.key] = crypto.decrypt(var.value_encrypted)
        if var.is_secret:
            secret_keys.append(var.key)
    source: dict
    if image:
        source = {"image": image}
    else:
        source = {"repo_url": app.repo_url, "branch": app.branch}
        if app.repo_token_encrypted:
            source["token"] = crypto.decrypt(app.repo_token_encrypted)
    build = (
        {"type": "dockerfile", "dockerfile": app.dockerfile_path, "context": app.build_context}
        if app.build_type == Application.BuildType.DOCKERFILE
        else {"type": "compose", "file": app.compose_file}
    )
    return {
        "action": "deploy",
        "app": {"id": str(app.pk), "slug": app.slug},
        "deployment": {"id": str(deployment.pk), "number": deployment.number},
        "source": source,
        "build": build,
        "run": {
            "command": list(app.start_command),
            "container_port": app.container_port,
            "host_port": app.host_port,
            "bind_address": app.bind_address,
            "env": env,
        },
        "secret_env_keys": secret_keys,
        "healthcheck": {"path": app.healthcheck_path, "timeout_seconds": app.healthcheck_timeout_seconds},
    }


@transaction.atomic
def _start(app: Application, *, actor, trigger: str, rollback_of: Deployment | None, request) -> Deployment:
    app = Application.objects.select_for_update().select_related("server", "organization").get(pk=app.pk)
    if app.server.status != Server.Status.ONLINE:
        raise Conflict(
            f"The server {app.server.name} is {app.server.status}. Its agent must be online to deploy."
        )
    if app.deployments.filter(status__in=Deployment.ACTIVE_STATUSES).exists():
        raise Conflict("A deployment of this application is already in progress.")
    number = (app.deployments.aggregate(n=Max("number"))["n"] or 0) + 1
    deployment = Deployment.objects.create(
        application=app,
        number=number,
        trigger=trigger,
        rollback_of=rollback_of,
        triggered_by=actor,
        branch="" if rollback_of else app.branch,
        commit_sha=rollback_of.commit_sha if rollback_of else "",
        image=rollback_of.image if rollback_of else "",
        task_expires_at=timezone.now() + timedelta(seconds=settings.TASK_TTL_SECONDS),
    )
    message = dispatch.build_task(
        task_id=str(deployment.pk),
        server_id=str(app.server_id),
        kind="deploy",
        payload=_payload(app, deployment, image=rollback_of.image if rollback_of else None),
        timeout_seconds=settings.DEPLOYMENT_TIMEOUT_SECONDS,
    )
    action = AuditAction.DEPLOYMENT_ROLLBACK if rollback_of else AuditAction.DEPLOYMENT_STARTED
    metadata = {"number": number, "branch": deployment.branch}
    if rollback_of:
        metadata = {"number": number, "to_number": rollback_of.number, "image": rollback_of.image}
    record(action, request=request, organization=app.organization, target=app, metadata=metadata)
    server_id = app.server_id
    transaction.on_commit(lambda: dispatch.send(server_id, message))
    _notify(app)
    return deployment


def start_deployment(app: Application, *, actor, request=None) -> Deployment:
    return _start(app, actor=actor, trigger=Deployment.Trigger.MANUAL, rollback_of=None, request=request)


def start_rollback(target: Deployment, *, actor, request=None) -> Deployment:
    if target.status != Deployment.Status.SUCCEEDED or not target.image:
        raise Conflict("Only a successful deployment with a built image can be restored.")
    if target.is_current:
        raise Conflict("This release is already the current one.")
    return _start(
        target.application,
        actor=actor,
        trigger=Deployment.Trigger.ROLLBACK,
        rollback_of=target,
        request=request,
    )


# --- Reports from the agent ------------------------------------------------------------------------


def _agent_deployment(server_id, task_id) -> Deployment | None:
    try:
        return (
            Deployment.objects.select_for_update()
            .select_related("application")
            .filter(pk=task_id, application__server_id=server_id)
            .first()
        )
    except (ValueError, TypeError):
        return None
    except Exception:  # malformed UUID from a misbehaving agent
        logger.warning("Invalid task id %r from agent %s", task_id, server_id)
        return None


@transaction.atomic
def record_logs(*, server_id, task_id, lines) -> bool:
    if not isinstance(lines, list):
        return False
    deployment = _agent_deployment(server_id, task_id)
    if deployment is None or deployment.status not in Deployment.ACTIVE_STATUSES:
        return False
    last = deployment.logs.aggregate(n=Max("seq"))["n"] or 0
    room = settings.DEPLOYMENT_LOG_MAX_LINES - last
    entries = []
    for line in lines[:500]:
        if room <= 0:
            break
        if not isinstance(line, dict) or not isinstance(line.get("message"), str):
            continue
        stream = line.get("stream") if line.get("stream") in ("stdout", "stderr", "system") else "stdout"
        last += 1
        room -= 1
        entries.append(
            DeploymentLog(
                deployment=deployment, seq=last, stream=stream, message=line["message"][:MAX_LOG_LINE]
            )
        )
    if room <= 0 and entries:
        entries[-1].message = "[log truncated: DEPLOYMENT_LOG_MAX_LINES reached]"
        entries[-1].stream = "system"
    DeploymentLog.objects.bulk_create(entries)
    return True


_TRANSITIONS = {
    Deployment.Status.QUEUED: {
        Deployment.Status.RUNNING,
        Deployment.Status.FAILED,
        Deployment.Status.SUCCEEDED,
    },
    Deployment.Status.RUNNING: {
        Deployment.Status.RUNNING,
        Deployment.Status.FAILED,
        Deployment.Status.SUCCEEDED,
    },
}


@transaction.atomic
def update_status(*, server_id, task_id, status, step="", error="", result=None) -> bool:
    deployment = _agent_deployment(server_id, task_id)
    if deployment is None or status not in _TRANSITIONS.get(deployment.status, set()):
        return False
    now = timezone.now()
    deployment.status = status
    fields = ["status"]
    if step:  # a failure report keeps the step where it happened
        deployment.step = str(step)[:32]
        fields.append("step")
    if status == Deployment.Status.RUNNING and deployment.started_at is None:
        deployment.started_at = now
        fields.append("started_at")
    if status in (Deployment.Status.SUCCEEDED, Deployment.Status.FAILED):
        deployment.finished_at = now
        fields.append("finished_at")
    if status == Deployment.Status.FAILED:
        deployment.error = str(error or "Deployment failed.")[:2000]
        fields.append("error")
    if status == Deployment.Status.SUCCEEDED:
        result = result if isinstance(result, dict) else {}
        if isinstance(result.get("commit_sha"), str):
            deployment.commit_sha = result["commit_sha"][:64]
        if isinstance(result.get("image"), str):
            deployment.image = result["image"][:255]
        Deployment.objects.filter(application_id=deployment.application_id, is_current=True).update(
            is_current=False
        )
        deployment.is_current = True
        fields += ["commit_sha", "image", "is_current"]
    deployment.save(update_fields=fields)
    _notify(deployment.application)
    return True


@transaction.atomic
def fail_stale_deployments() -> int:
    now = timezone.now()
    never_started = Deployment.objects.filter(
        status=Deployment.Status.QUEUED, task_expires_at__lt=now
    ).select_related("application")
    timed_out = Deployment.objects.filter(
        status=Deployment.Status.RUNNING,
        started_at__lt=now - timedelta(seconds=settings.DEPLOYMENT_TIMEOUT_SECONDS + 120),
    ).select_related("application")
    count = 0
    for deployments, reason in (
        (never_started, "The agent did not pick up the task in time (offline or disconnected)."),
        (timed_out, "The agent stopped reporting progress before the deployment timeout."),
    ):
        for deployment in deployments.select_for_update():
            deployment.status = Deployment.Status.FAILED
            deployment.error = reason
            deployment.finished_at = now
            deployment.save(update_fields=["status", "error", "finished_at"])
            _notify(deployment.application)
            count += 1
    return count
