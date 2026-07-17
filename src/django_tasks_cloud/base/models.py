import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.tasks import TaskResultStatus
from django.utils import timezone

DEFAULT_TOKEN_TTL_DAYS = settings.DEFAULT_TOKEN_TTL_DAYS


class TaskResult(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    task = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=10, choices=TaskResultStatus.choices)

    enqueued_at = models.DateTimeField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    last_attempted_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    worker_ids = models.JSONField(blank=True, null=True, default=list)
    backend = models.CharField(max_length=255, blank=True, null=True)
    errors = models.JSONField(blank=True, null=True, default=list)

    args = models.JSONField(blank=True, null=True, default=list)
    kwargs = models.JSONField(blank=True, null=True, default=dict)

    class Meta:
        verbose_name = "Task Result"
        verbose_name_plural = "Task Results"
