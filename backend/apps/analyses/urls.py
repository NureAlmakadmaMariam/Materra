from django.urls import path

from .views import AnalysisCreateView, AnalysisDetailView, AnalysisImageView

app_name = 'analyses'

urlpatterns = [
    path('', AnalysisCreateView.as_view(), name='create'),
    path('<uuid:pk>/', AnalysisDetailView.as_view(), name='detail'),
    path('<uuid:pk>/image/', AnalysisImageView.as_view(), name='image'),
]
