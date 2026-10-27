from django.urls import path

from . import views

urlpatterns = [
    path("appointments/<int:appointment_id>/consult/", views.consult, name="consult"),
    path("appointments/<int:appointment_id>/prescriptions/add/", views.prescription_add, name="prescription_add"),
    path("appointments/<int:appointment_id>/prescriptions/<int:prescription_id>/delete/", views.prescription_delete, name="prescription_delete"),
    path("consultations/<int:consultation_id>/", views.consultation_detail, name="consultation_detail"),
    path("my-records/", views.my_records, name="my_records"),
    path("reports/", views.report_list, name="report_list"),
    path("reports/upload/", views.report_upload, name="report_upload"),
    path("reports/<int:report_id>/download/", views.report_download, name="report_download"),
    path("reports/<int:report_id>/delete/", views.report_delete, name="report_delete"),
]
