from datetime import datetime, timezone
from json import dumps
from traceback import format_exc
from typing import Any, Callable

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage, ServiceBusSender
from azure.servicebus.exceptions import ServiceBusError
from django.core.exceptions import ImproperlyConfigured
from django.tasks import Task, TaskResult, TaskResultStatus
from django.tasks.backends.base import BaseTaskBackend
from django.tasks.base import TaskError
from django.utils.module_loading import import_string


class _ServiceBusBaseBackend(BaseTaskBackend):
    supports_defer = True
    supports_get_result = True

    _default_destination_config_key: str

    def __init__(self, alias, params):
        super().__init__(alias, params)

        self.default_destination_name = self.options.get(
            self._default_destination_config_key
        )
        if not self.default_destination_name:
            raise ImproperlyConfigured(f"Unset: {self._default_destination_config_key}")

        self.use_connection_string = self.options.get(
            "SERVICEBUS_USE_CONNECTION_STRING",
            True,
        )

        if self.use_connection_string:
            self.connection_string = self.options.get("SERVICEBUS_CONNECTION_STRING")
            if not self.connection_string:
                raise ImproperlyConfigured("Unset: SERVICEBUS_CONNECTION_STRING")

            self.servicebus_client = ServiceBusClient.from_connection_string(
                self.connection_string
            )
        else:
            self.servicebus_namespace = self.options.get("SERVICEBUS_NAMESPACE_FQDN")
            if not self.servicebus_namespace:
                raise ImproperlyConfigured("Unset: SERVICEBUS_NAMESPACE_FQDN")

            credential_loader = self.options.get("SERVICEBUS_CREDENTIAL_LOADER")
            if not credential_loader:
                self.servicebus_client = ServiceBusClient(
                    self.servicebus_namespace, credential=DefaultAzureCredential()
                )
            else:
                self.servicebus_client = ServiceBusClient(
                    self.servicebus_namespace,
                    credential=import_string(credential_loader)(),
                )

        self._senders = {}

    def _get_sender(
        self, destination_name: str, getter_method: Callable[[Any], ServiceBusSender]
    ):
        if destination_name not in self._senders:
            self._senders[destination_name] = getter_method(destination_name)
        return self._senders[destination_name]

    def enqueue(self, task: Task, args, kwargs) -> TaskResult:
        self.validate_task(task)

        destination_name = task.queue_name or self.default_destination_name
        sender = self._get_destination_sender(  # type: ignore[reportAttributeAccessIssue]
            destination_name
        )  # Implemented in: Subclasses
        payload = {
            "task": task.name,
            "args": args,
            "kwargs": kwargs,
        }
        message = ServiceBusMessage(dumps(payload))
        task_result = TaskResult(
            task=task,
            id=message.message_id,  # type: ignore[reportArgumentType]
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
            if task.run_after:
                sender.schedule_messages(
                    message,
                    schedule_time_utc=task.run_after
                    if task.run_after.tzname() == "UTC"
                    else task.run_after.astimezone(timezone.utc),
                    timeout=5,
                )
            else:
                sender.send_messages(message, timeout=5)
            object.__setattr__(task_result, "enqueued_at", datetime.now(timezone.utc))
        except ServiceBusError as exc:
            task_error = TaskError(
                exception_class_path=f"{exc.__class__.__module__}.{exc.__class__.__qualname__}",
                traceback=format_exc(),
            )
            task_result.errors.append(task_error)
            object.__setattr__(task_result, "status", TaskResultStatus.FAILED)

        return task_result

    def get_result(self, result_id):
        # TODO: Implement Persistence (with views and database to persist results)
        return super().get_result(result_id)

    def close(self):
        for sender in self._senders.values():
            sender.close()
        self._senders.clear()
        self.servicebus_client.close()


class ServiceBusQueueBackend(_ServiceBusBaseBackend):
    _default_destination_config_key: str = "SERVICEBUS_DEFAULT_QUEUE_NAME"

    def _get_destination_sender(self, queue_name):
        return self._get_sender(queue_name, self.servicebus_client.get_queue_sender)


class ServiceBusTopicBackend(_ServiceBusBaseBackend):
    _default_destination_config_key: str = "SERVICEBUS_DEFAULT_TOPIC_NAME"

    def _get_destination_sender(self, topic_name):
        return self._get_sender(topic_name, self.servicebus_client.get_topic_sender)
