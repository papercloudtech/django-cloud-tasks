from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.tasks import TaskResultStatus
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TaskResult


def _apply_status_transition(task_result, new_status, payload):
    now = timezone.now()
    current_status = task_result.status

    if new_status == TaskResultStatus.READY:
        if not task_result.enqueued_at:
            task_result.enqueued_at = now

    elif new_status == TaskResultStatus.RUNNING:
        if current_status not in (
            TaskResultStatus.READY,
            TaskResultStatus.RUNNING,
        ):
            raise ValidationError({"status": "Invalid Transition to: RUNNING"})
        if not task_result.started_at:
            task_result.started_at = now
        task_result.last_attempted_at = now

    elif new_status == TaskResultStatus.FAILED:
        if current_status not in (
            TaskResultStatus.RUNNING,
            TaskResultStatus.READY,
        ):
            raise ValidationError({"status": "Invalid Transition to: FAILED"})
        if not task_result.finished_at:
            task_result.finished_at = now

    elif new_status == TaskResultStatus.SUCCESSFUL:
        if current_status != TaskResultStatus.RUNNING:
            raise ValidationError({"status": "Invalid Transition to: SUCCESSFUL"})
        if not task_result.finished_at:
            task_result.finished_at = now

    task_result.status = new_status

    worker_id = payload.get("worker_id")
    if worker_id:
        worker_ids = task_result.worker_ids or []
        if worker_id not in worker_ids:
            worker_ids.append(worker_id)
        task_result.worker_ids = worker_ids

    error = payload.get("error")
    if error:
        errors = task_result.errors or []
        errors.append(error)
        task_result.errors = errors


@csrf_exempt
@require_POST
def update_task_status(request, task_id):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise PermissionDenied

    if not user.has_perm("django_tasks_cloud.change_taskresult"):
        raise PermissionDenied

    try:
        task_result = TaskResult.objects.get(id=task_id)
    except TaskResult.DoesNotExist:
        return JsonResponse({"detail": "Not Found"}, status=404)

    try:
        import json

        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"detail": "Invalid JSON Payload"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"detail": "Invalid JSON Payload"}, status=400)

    status = payload.get("status")
    if status not in TaskResultStatus.values:
        return JsonResponse({"detail": "Invalid/Missing Status"}, status=400)

    try:
        _apply_status_transition(task_result, status, payload)
        task_result.full_clean()
        task_result.save(
            update_fields=[
                "status",
                "enqueued_at",
                "started_at",
                "last_attempted_at",
                "finished_at",
                "worker_ids",
                "errors",
            ]
        )
    except ValidationError as exc:
        return JsonResponse({"detail": exc.message_dict}, status=400)

    return JsonResponse(
        {
            "id": task_result.id,
            "status": task_result.status,
            "enqueued_at": task_result.enqueued_at,
            "started_at": task_result.started_at,
            "last_attempted_at": task_result.last_attempted_at,
            "finished_at": task_result.finished_at,
        }
    )
