from django.urls import path

from .views import ReportDownloadView

app_name = 'reports'

urlpatterns = [
    path('<uuid:pk>/download/', ReportDownloadView.as_view(), name='download'),
]
