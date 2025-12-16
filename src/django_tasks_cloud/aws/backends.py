from datetime import datetime, timezone
from json import dumps
from traceback import format_exc

import boto3
from botocore.exceptions import ClientError as BotoClientError
from django.core.exceptions import ImproperlyConfigured
from django.tasks import Task, TaskResult, TaskResultStatus
from django.tasks.backends.base import BaseTaskBackend
from django.tasks.base import TaskError


class AWSBaseBackend(BaseTaskBackend):
    supports_get_result = True

    def __init__(self, alias, params):
        super().__init__(alias, params)
        self.region_name = self.options.get("AWS_REGION")
        if not self.region_name:
            raise ImproperlyConfigured("Unset: AWS_REGION")

    def _publish_message(self, task: Task, payload: dict) -> str:
        raise NotImplementedError

    def enqueue(self, task: Task, args, kwargs) -> TaskResult:
        self.validate_task(task)

        payload = {
            "task": task.name,
            "args": args,
            "kwargs": kwargs,
        }

        task_result = TaskResult(
            task=task,
            id=None,
            status=TaskResultStatus.READY,
            enqueued_at=None,
            started_at=None,
            finished_at=None,
            last_attempted_at=None,
            args=args,
            kwargs=kwargs,
            backend=self.alias,
            errors=[],
            worker_ids=[],
        )

        try:
            message_id = self._publish_message(task, payload)
            object.__setattr__(task_result, "id", message_id)
            object.__setattr__(task_result, "enqueued_at", datetime.now(timezone.utc))

        except BotoClientError as exc:
            task_error = TaskError(
                exception_class_path=f"{exc.__class__.__module__}.{exc.__class__.__qualname__}",
                traceback=format_exc(),
            )
            task_result.errors.append(task_error)
            object.__setattr__(task_result, "status", TaskResultStatus.FAILED)

        return task_result


class SQSBackend(AWSBaseBackend):
    def __init__(self, alias, params):
        super().__init__(alias, params)

        self.default_queue_name = self.options.get("AWS_DEFAULT_QUEUE_NAME")
        if not self.default_queue_name:
            raise ImproperlyConfigured("Unset: AWS_DEFAULT_QUEUE_NAME")

        self.sqs_client = boto3.client("sqs", region_name=self.region_name)
        self._queue_urls = {}

    def _get_queue_url(self, queue_name: str) -> str:
        if queue_name not in self._queue_urls:
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            self._queue_urls[queue_name] = response["QueueUrl"]

        return self._queue_urls[queue_name]

    def _publish_message(self, task: Task, payload: dict) -> str:
        queue_name = task.queue_name or self.default_queue_name
        queue_url = self._get_queue_url(queue_name)
        response = self.sqs_client.send_message(
            QueueUrl=queue_url, MessageBody=dumps(payload)
        )

        return response.get("MessageId")


class SNSTopicBackend(AWSBaseBackend):
    def __init__(self, alias, params):
        super().__init__(alias, params)

        self.default_topic = self.options.get("AWS_DEFAULT_TOPIC_NAME")
        if not self.default_topic:
            raise ImproperlyConfigured("Unset: AWS_DEFAULT_TOPIC_NAME")

        self.sns_arn_prefix = self.options.get("AWS_SNS_ARN_PREFIX")
        if not self.sns_arn_prefix:
            raise ImproperlyConfigured(
                "Unset: AWS_SNS_ARN_PREFIX (e.g., arn:aws:sns:region:account_id:)"
            )

        self.sns_client = boto3.client("sns", region_name=self.region_name)

    def _publish_message(self, task: Task, payload: dict) -> str:
        topic_arn = self.sns_arn_prefix + task.queue_name or self.default_topic
        response = self.sns_client.publish(TopicArn=topic_arn, Message=dumps(payload))

        return response.get("MessageId")


class EventBridgeSchedulerBackend(AWSBaseBackend):
    supports_defer = True

    def __init__(self, alias, params):
        super().__init__(alias, params)

        self.default_queue_name = self.options.get("AWS_DEFAULT_SQS_QUEUE_NAME")
        if not self.default_queue_name:
            raise ImproperlyConfigured(f"Unset: AWS_DEFAULT_SQS_QUEUE_NAME")

        self.scheduler_role_arn = self.options.get("EVENTBRIDGE_SCHEDULER_ROLE_ARN")
        if not self.scheduler_role_arn:
            raise ImproperlyConfigured("Unset: EVENTBRIDGE_SCHEDULER_ROLE_ARN")

        self.sqs_client = boto3.client("sqs", region_name=self.region_name)
        self.scheduler_client = boto3.client("scheduler", region_name=self.region_name)
        self._queue_arns = {}

    def _get_queue_arn(self, queue_name):
        if queue_name not in self._queue_arns:
            try:
                response = self.sqs_client.get_queue_url(QueueName=queue_name)
                queue_url = response["QueueUrl"]

                attrs = self.sqs_client.get_queue_attributes(
                    QueueUrl=queue_url, AttributeNames=["QueueArn"]
                )
                self._queue_arns[queue_name] = attrs["Attributes"]["QueueArn"]

            except BotoClientError as e:
                raise ImproperlyConfigured(
                    f"SQS: Not Found: '{queue_name}' for EventBridge Target: {e}"
                ) from e

        return self._queue_arns[queue_name]

    def _publish_message(self, task: Task, payload: dict) -> str:
        destination_queue_name = task.queue_name or self.default_queue_name
        queue_arn = self._get_queue_arn(destination_queue_name)

        if task.run_after is None:
            # WARNING
            object.__setattr__(task, "run_after", datetime.now(timezone.utc))

        schedule_time = (
            task.run_after.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")  # type: ignore
        )
        schedule_name = (
            f"django-task-{task.name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        self.scheduler_client.create_schedule(
            Name=schedule_name,
            ScheduleExpression=f"at({schedule_time})",
            ScheduleExpressionTimezone="UTC",
            State="ENABLED",
            ActionAfterCompletion="DELETE",
            FlexibleTimeWindow={"Mode": "OFF"},
            Target={
                "Arn": queue_arn,
                "RoleArn": self.scheduler_role_arn,
                "Input": dumps(payload),
            },
        )
        return schedule_name


class AWSLambdaBackend(AWSBaseBackend):
    supports_get_result = False

    def __init__(self, alias, params):
        super().__init__(alias, params)

        self.default_function_name = self.options.get(
            "AWS_DEFAULT_LAMBDA_FUNCTION_NAME"
        )
        if not self.default_function_name:
            raise ImproperlyConfigured("Unset: AWS_DEFAULT_LAMBDA_FUNCTION_NAME")

        self.lambda_client = boto3.client("lambda", region_name=self.region_name)

    def _publish_message(self, task: Task, payload: dict) -> str:
        function_name = task.queue_name or self.default_function_name

        response = self.lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=dumps(payload),
        )

        return response.get("ResponseMetadata", {}).get("RequestId")
