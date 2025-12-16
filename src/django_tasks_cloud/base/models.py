from django.db import models
from django.tasks import TaskResultStatus


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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    _FROZEN_ONCE_SET = ("id", "enqueued_at", "args", "kwargs")

    def save(self, *args, **kwargs):
        if self._state.adding:
            super().save(*args, **kwargs)
            return

        orig = TaskResult.objects.filter(pk=self.pk).first()
        if not orig:
            super().save(*args, **kwargs)
            return

        if orig.id and self.id != orig.id:
            raise ValueError("Frozen: id")

        if orig.enqueued_at is not None and self.enqueued_at != orig.enqueued_at:
            raise ValueError("Frozen: enqueued_at")

        if orig.args not in (None, [], {}) and self.args != orig.args:
            raise ValueError("Frozen: args")

        if orig.kwargs not in (None, {}, []) and self.kwargs != orig.kwargs:
            raise ValueError("Frozen: kwargs")

        super().save(*args, **kwargs)
