from django.contrib.auth.models import Permission, User
from django.tasks import TaskResultStatus
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from django_tasks_cloud.base.models import TaskResult


class UpdateTaskStatusViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="worker", password="pass")
        self.permission = Permission.objects.get(codename="change_taskresult")
        self.user.user_permissions.add(self.permission)
        self.task = TaskResult.objects.create(
            id="task-1",
            status=TaskResultStatus.READY,
        )
        self.url = reverse("update_task_status", args=[self.task.id])

    def authenticate(self):
        self.client.force_login(self.user)

    def test_requires_authentication(self):
        response = self.client.post(self.url, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_requires_permission(self):
        self.user.user_permissions.clear()
        self.authenticate()
        response = self.client.post(self.url, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_returns_404_for_missing_task(self):
        self.authenticate()
        url = reverse("update_task_status", args=["missing"])
        response = self.client.post(url, content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_rejects_invalid_json(self):
        self.authenticate()
        response = self.client.post(self.url, data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_rejects_missing_status(self):
        self.authenticate()
        response = self.client.post(
            self.url, data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_status(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data='{"status": "INVALID"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_valid_transition_to_running(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data='{"status": "%s"}' % TaskResultStatus.RUNNING,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskResultStatus.RUNNING)
        self.assertIsNotNone(self.task.started_at)
        self.assertIsNotNone(self.task.last_attempted_at)

    def test_invalid_transition_to_successful(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data='{"status": "%s"}' % TaskResultStatus.SUCCESSFUL,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_successful_terminal_transition(self):
        self.task.status = TaskResultStatus.RUNNING
        self.task.started_at = timezone.now()
        self.task.save()
        self.authenticate()
        response = self.client.post(
            self.url,
            data='{"status": "%s"}' % TaskResultStatus.SUCCESSFUL,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskResultStatus.SUCCESSFUL)
        self.assertIsNotNone(self.task.finished_at)

    def test_worker_id_is_recorded(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data='{"status": "%s", "worker_id": "w1"}' % TaskResultStatus.RUNNING,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertIn("w1", self.task.worker_ids)

    def test_error_is_appended(self):
        self.task.status = TaskResultStatus.RUNNING
        self.task.started_at = timezone.now()
        self.task.save()
        self.authenticate()
        response = self.client.post(
            self.url,
            data='{"status": "%s", "error": "boom"}' % TaskResultStatus.FAILED,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertIn("boom", self.task.errors)
        self.assertEqual(self.task.status, TaskResultStatus.FAILED)
        self.assertIsNotNone(self.task.finished_at)
