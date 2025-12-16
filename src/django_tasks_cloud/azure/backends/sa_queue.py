from datetime import datetime, timezone
from json import dumps
from traceback import format_exc

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.queue import (
    QueueClient,
    QueueServiceClient,
)
from django.core.exceptions import ImproperlyConfigured
from django.tasks import Task, TaskResult, TaskResultStatus
from django.tasks.backends.base import BaseTaskBackend
from django.tasks.base import TaskError
from django.utils.module_loading import import_string


class StorageAccountQueueBackend(BaseTaskBackend):
    supports_get_result = True

    def __init__(self, alias, params):
        super().__init__(alias, params)

        self.default_destination_name = self.options.get(
            "STORAGE_ACCOUNT_QUEUE_DEFAULT_QUEUE_NAME"
        )
        if not self.default_destination_name:
            raise ImproperlyConfigured(
                f"Unset: STORAGE_ACCOUNT_QUEUE_DEFAULT_QUEUE_NAME"
            )

        self.use_connection_string = self.options.get(
            "STORAGE_ACCOUNT_USE_CONNECTION_STRING",
            True,
        )

        if self.use_connection_string:
            self.connection_string = self.options.get(
                "STORAGE_ACCOUNT_CONNECTION_STRING"
            )
            if not self.connection_string:
                raise ImproperlyConfigured("Unset: STORAGE_ACCOUNT_CONNECTION_STRING")

            self.queue_service_client = QueueServiceClient.from_connection_string(
                self.connection_string
            )
        else:
            self.storage_account_url = self.options.get("STORAGE_ACCOUNT_URL")
            if not self.storage_account_url:
                raise ImproperlyConfigured("Unset: STORAGE_ACCOUNT_URL")

            credential_loader = self.options.get("STORAGE_ACCOUNT_CREDENTIAL_LOADER")
            if not credential_loader:
                self.queue_service_client = QueueServiceClient(
                    self.storage_account_url, credential=DefaultAzureCredential()
                )
            else:
                self.queue_service_client = QueueServiceClient(
                    self.storage_account_url,
                    credential=import_string(credential_loader)(),
                )

        self._queue_clients: dict[str, QueueClient] = {}

    def _get_queue_client(self, queue_name: str) -> QueueClient:
        if queue_name not in self._queue_clients:
            self._queue_clients[queue_name] = (
                self.queue_service_client.get_queue_client(queue=queue_name)
            )

        return self._queue_clients[queue_name]

    def enqueue(self, task: Task, args, kwargs) -> TaskResult:
        self.validate_task(task)

        destination_name = task.queue_name or self.default_destination_name
        queue_client = self._get_queue_client(destination_name)

        payload = {
            "task": task.name,
            "args": args,
            "kwargs": kwargs,
        }
        message_content = dumps(payload)
        task_result = TaskResult(
            task=task,
            id=None,
            status=TaskResultStatus.READY,
            enqueued_at=None,
            started_at=None,
            last_attempted_at=None,
            finished_at=None,
            args=args,
            kwargs=kwargs,
            backend=self.alias,
            errors=[],
            worker_ids=[],
        )

        try:
            result = queue_client.send_message(message_content, timeout=5)
            object.__setattr__(task_result, "enqueued_at", datetime.now(timezone.utc))
            object.__setattr__(task_result, "id", result.id)
        except AzureError as exc:
            task_error = TaskError(
                exception_class_path=f"{exc.__class__.__module__}.{exc.__class__.__qualname__}",
                traceback=format_exc(),
            )
            task_result.errors.append(task_error)
            object.__setattr__(task_result, "status", TaskResultStatus.FAILED)

        return task_result

    def get_result(self, result_id):
        return super().get_result(result_id)
