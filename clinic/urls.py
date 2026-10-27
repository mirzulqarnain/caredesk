from django.urls import path

from . import views

urlpatterns = [
    path("doctors/", views.doctors, name="doctors"),
    path("doctors/<int:doctor_id>/", views.doctor_detail, name="doctor_detail"),
    path("schedule/<int:doctor_id>/", views.schedule_manage, name="schedule_manage"),
    path("schedule/<int:doctor_id>/<int:schedule_id>/delete/", views.schedule_delete, name="schedule_delete"),
    path("patients/", views.patients, name="patients"),
    path("patients/new/", views.patient_create, name="patient_create"),
    path("patients/<int:user_id>/", views.patient_detail, name="patient_detail"),
]
