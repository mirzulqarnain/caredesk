from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("clinic.urls")),
    path("", include("appointments.urls")),
    path("", include("records.urls")),
    path("", include("billing.urls")),
    path("", include("dashboard.urls")),
]

if not settings.USE_S3:
    # Local development: serve uploaded files from the /media folder.
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]

handler403 = "dashboard.views.error_403"
handler404 = "dashboard.views.error_404"
handler500 = "dashboard.views.error_500"
