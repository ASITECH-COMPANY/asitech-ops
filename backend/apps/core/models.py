import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base: UUID primary key (never guessable) and timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
