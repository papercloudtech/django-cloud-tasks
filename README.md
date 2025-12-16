# Django Task Backend for AWS and Azure

[![Build and Push to PyPI (and Test PyPI for testing)](https://github.com/papercloudtech/django-tasks-cloud/actions/workflows/cd.yml/badge.svg)](https://github.com/papercloudtech/django-tasks-cloud/actions/workflows/cd.yml)

> ❌ **IMPORTANT**
> This project is in its early stages. While it is functional, it may not cover all edge cases or have comprehensive documentation. Use it at your own risk and feel free to contribute! We are working fast to make it production-ready.

This project aims to use Django's new `Task` back-end to expose AWS and Azure native services to manage long-running tasks asynchronously. This project is useful for tasks that must run outside the request-response cycle, like sending emails, processing images, or running machine learning models. It leverages the power of AWS and Azure native services. You can choose between the two cloud providers (more on this in the installation and setup sections). With the reliance on cloud native services, the project provides a scalable and reliable solution for managing long-running tasks.

## Installation

Installation depends on which cloud provider you want to use. You can install the package using PIP for all cloud providers as follows:

For AWS:

```bash
pip install django-tasks-cloud[aws]
```

For Azure:

```bash
pip install django-tasks-cloud[azure]
```

For support for both AWS and Azure:

```bash
pip install django-tasks-cloud[aws,azure]
```

> [!NOTE]
> There is a package with very similar name called `django-cloud-tasks`. Ensrue you install `django-tasks-cloud`. Also, running the above command will install the core package without any cloud provider-specific dependencies. You must install the cloud provider-specific dependencies separately as mentioned below.

Once installed, add it to your Django `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    ...
    "django_cloud_task.base",
    # Either or Both
    "django_tasks_cloud.aws",  # For AWS
    "django_tasks_cloud.azure",  # For Azure
    ...
]
```

If you want to work with the nightly builds, please install it from Test PyPI as follows:

```bash
pip install -i https://test.pypi.org/simple/ django-tasks-cloud
```

The CD pipeline automatically publishes to Test PyPI on every commit to the `main` branch. Production releases are published to the official PyPI repository on every tagged release.

## Configuration

### AWS: SNS

```python
TASKS = {
    "default": {
        "BACKEND": "cloud_tasks_aws.backends.SNSTopicBackend",
        "QUEUES": ["email-ingestor"],
        "OPTIONS": {
            "AWS_DEFAULT_TOPIC_NAME": "testing",
            "AWS_SNS_ARN_PREFIX": "arn:aws:sns:<region>:<account-number>:",
            "AWS_REGION": "ap-south-1",
        },
    },
}
```

Each entry in `QUEUES` corresponds to an SNS topic that you have created in your AWS account. The `AWS_DEFAULT_TOPIC_NAME` is the default topic that will be used if no specific topic is mentioned when creating a task.

### AWS: SQS

```python
TASKS = {
    "default": {
        "BACKEND": "cloud_tasks_aws.backends.SQSBackend",
        "QUEUES": ["email-ingestor"],
        "OPTIONS": {
            "AWS_DEFAULT_QUEUE_NAME": "testing",
            "AWS_REGION": "ap-south-1",
        },
    },
}
```

Each entry in `QUEUES` corresponds to an SQS queue that you have created in your AWS account. The `AWS_DEFAULT_QUEUE_NAME` is the default queue that will be used if no specific queue is mentioned when creating a task.

### AWS: EventBridge

In this setup, EventBridge Scheduler is used to schedule tasks that will be sent to SQS queues. Since SQS and SNS doesn't support per-message scheduling natively, EventBridge Scheduler acts as an intermediary to handle the scheduling.

```python
TASKS = {
    "eventbridge_scheduler": {
        "BACKEND": "cloud_tasks_aws.backends.EventBridgeSchedulerBackend",
        "QUEUES": ["email-ingestor"],
        "OPTIONS": {
            "AWS_DEFAULT_SQS_QUEUE_NAME": "testing",
            "EVENTBRIDGE_SCHEDULER_ROLE_ARN": "",
            "AWS_REGION": "ap-south-1",
        },
    },
}
```

Each name in the `QUEUES` list corresponds to an SQS queue that you have created in your AWS account. EventBridge Scheduler, once the time is due, will send the task to the specified SQS queue. The `AWS_DEFAULT_SQS_QUEUE_NAME` is the default queue that will be used if no specific queue is mentioned when creating a task.

### AWS: Async Lambda Invocation

With this back-end, you can invoke AWS Lambda functions asynchronously. This is useful for tasks that can be handled by serverless functions.

```python
TASKS = {
    "default": {
        "BACKEND": "cloud_tasks_aws.backends.LambdaAsyncInvocationBackend",
        "QUEUES": ["email-ingestor"],
        "OPTIONS": {
            "AWS_DEFAULT_LAMBDA_FUNCTION_NAME": "testing",
            "AWS_REGION": "ap-south-1",
        },
    },
}
```

Each name in the `QUEUES` list corresponds to a Lambda function that you have created in your AWS account. The `AWS_DEFAULT_LAMBDA_FUNCTION_NAME` is the default Lambda function that will be used if no specific function is mentioned when creating a task.

### Azure: Service Bus Queue

```python
TASKS = {
    "default": {
        "BACKEND": "django_cloud_tasks_azure.backends.service_bus.ServiceBusQueueBackend",
        "QUEUES": ["default"],
        "OPTIONS": {
            "SERVICEBUS_DEFAULT_QUEUE_NAME": "testing",
            "SERVICEBUS_USE_CONNECTION_STRING": True,
            "SERVICEBUS_CONNECTION_STRING": "",
            "SERVICEBUS_NAMESPACE_FQDN": "",
            "SERVICEBUS_CREDENTIAL_LOADER": "this.that.custom_credential_loader_function",
        },
    },
}
```

For a simple setup, you can use the `SERVICEBUS_USE_CONNECTION_STRING` option set to `True` and provide the `SERVICEBUS_CONNECTION_STRING`. This connection string can be obtained from the Azure portal.

If you don't wanna hardcode credentials, you must provide the `SERVICEBUS_NAMESPACE_FQDN` and provide `SERVICEBUS_CREDENTIAL_LOADER`. If you don't provide a custom credential loader, the default will use `DefaultAzureCredential` from the `azure-identity` package.

To use a custom credential class from a suite of Azure credential classes, set the `SERVICEBUS_CREDENTIAL_LOADER` option to a method of the following function signature:

```python
def custom_credential_loader() -> TokenCredential: ...
```

Mention it's full module path in the `SERVICEBUS_CREDENTIAL_LOADER` setting. The function must return an instance of a class that inherits from `azure.core.credentials.TokenCredential`. A function wrapper is required because some `TokenCredential` classes require parameters for initialization. To know more about the available credential classes, refer to the [Azure Identity](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity?view=azure-python) documentation.

> [!IMPORTANT]
> `QUEUES` is a list of queue names that you want to use. Each queue name in the list corresponds to a queue that you have created in your Azure Service Bus namespace.

### Azure: Service Bus Topic

```python
TASKS = {
    "default": {
        "BACKEND": "django_cloud_tasks_azure.backends.service_bus.ServiceBusTopicBackend",
        "QUEUES": ["default"],
        "OPTIONS": {
            "SERVICEBUS_DEFAULT_TOPIC_NAME": "testing",
            "SERVICEBUS_USE_CONNECTION_STRING": True,
            "SERVICEBUS_CONNECTION_STRING": "",
            "SERVICEBUS_NAMESPACE_FQDN": "",
            "SERVICEBUS_CREDENTIAL_LOADER": "this.that.custom_credential_loader_function",
        },
    },
}
```

The configuration is similar to the Service Bus Queue backend. The main difference is that you need to provide the `SERVICEBUS_DEFAULT_TOPIC_NAME` instead of the queue name.

### Azure: Storage Account Queue

```python
TASKS = {
    "sa_queue": {
        "BACKEND": "cloud_tasks_azure.backends.sa_queue.StorageAccountQueueBackend",
        "QUEUES": ["email-ingestor"],
        "OPTIONS": {
            "STORAGE_ACCOUNT_QUEUE_DEFAULT_QUEUE_NAME": "testing",
            "STORAGE_ACCOUNT_USE_CONNECTION_STRING": True,
            "STORAGE_ACCOUNT_CONNECTION_STRING": "",
            "STORAGE_ACCOUNT_URL": "",
            "STORAGE_ACCOUNT_CREDENTIAL_LOADER": "this.that.custom_credential_loader_function",
        },
    },
}
```

The configuration is similar to the Service Bus Queue backend. The main difference is that you need to provide the `STORAGE_ACCOUNT_QUEUE_DEFAULT_QUEUE_NAME` instead of the queue name.

## Taks Result Management

For all back-ends, the payload sent to the cloud provider will be a JSON object with the following structure:

```json
{
    "task_name": "function_name",
    "args": [/* positional arguments */],
    "kwargs": { /* keyword arguments */ },
}
```

The task name will be the name of the function you decorated with `@task`. The `args` and `kwargs` will contain the positional and keyword arguments passed to the task when it was called. So the function you define is merely a signature. You can either keep it a signature, or implement it and use the same codebase in the runner that processes the tasks.

Once you enqueue a task, you'll immediately receive a `TaskResult` object. You can use this to later track the status of the task. However, note that the actual execution and result tracking of the task is outside the scope of this package. While implementing the remote worker, you must write logic to call back your Django application at a particular endpoint to update the task status and result. Note that database persistence is still a work in progress and will be added in future releases.

## Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](./CONTRIBUTING.md) file for more information on how to contribute to this project.

PaperCloud is an organization aimimg to contirbute to society by building open-source software for the community. We are a group of passionate engineers who consider _engineering as responsibility_. If you want to know more about us, visit [papercloud.tech](https://papercloud.tech).
