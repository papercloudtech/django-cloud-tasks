from django.urls import path

from .views import update_task_status

urlpatterns = [
    path("tasks/<str:task_id>/status/", update_task_status, name="update_task_status"),
]
