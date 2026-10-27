from django.urls import path

from . import views

urlpatterns = [
    path("appointments/", views.appointment_list, name="appointment_list"),
    path("appointments/book/", views.book, name="book"),
    path("appointments/<int:appointment_id>/", views.appointment_detail, name="appointment_detail"),
    path("appointments/<int:appointment_id>/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("appointments/<int:appointment_id>/no-show/", views.appointment_no_show, name="appointment_no_show"),
]
