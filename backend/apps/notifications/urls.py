from django.urls import path

from .views import NotificationListView, NotificationPreferenceView, NotificationReadView

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
    path("notifications/<int:notification_id>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("notifications/<int:notification_id>/", NotificationReadView.as_view(), name="notification-delete"),
]
