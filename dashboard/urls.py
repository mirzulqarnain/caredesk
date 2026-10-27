from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("my-health/", views.patient_dashboard, name="patient_dashboard"),
    path("today/", views.doctor_dashboard, name="doctor_dashboard"),
    path("desk/", views.desk_dashboard, name="desk_dashboard"),
    path("panel/", views.panel, name="panel"),
    path("panel/users/", views.panel_users, name="panel_users"),
    path("panel/users/new/", views.panel_user_create, name="panel_user_create"),
    path("panel/users/<int:user_id>/", views.panel_user_update, name="panel_user_update"),
    path("panel/system/", views.panel_system, name="panel_system"),
    path("panel/system/test-storage/", views.panel_s3_test, name="panel_s3_test"),
]
