from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.analyses.views import DashboardView, LandingView

# Admin is intentionally mounted at a non-default path (security rule §10.8).
urlpatterns = [
    path('materra-admin/', admin.site.urls),
    path('api/v1/analyses/', include('apps.analyses.urls')),
    path('api/v1/reports/',  include('apps.reports.urls')),
    path('',                 include('apps.accounts.urls')),
    # / → public landing page (redirects authenticated users to /dashboard/).
    path('',           LandingView.as_view(), name='home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]

# Raw dev upload tester — kept at /dev/ so it never collides with the
# root dashboard.  Only active when DEBUG=True.
if settings.DEBUG:
    from apps.analyses.views import DevUploadView
    urlpatterns += [path('dev/', DevUploadView.as_view(), name='dev-upload')]
