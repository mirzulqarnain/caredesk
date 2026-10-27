from django.urls import path

from . import views

urlpatterns = [
    path("billing/", views.invoice_list, name="invoice_list"),
    path("billing/new/", views.invoice_create, name="invoice_create"),
    path("billing/from-appointment/<int:appointment_id>/", views.invoice_from_appointment, name="invoice_from_appointment"),
    path("billing/<int:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("billing/<int:invoice_id>/items/add/", views.item_add, name="item_add"),
    path("billing/<int:invoice_id>/items/<int:item_id>/delete/", views.item_delete, name="item_delete"),
    path("billing/<int:invoice_id>/payments/add/", views.payment_add, name="payment_add"),
    path("billing/<int:invoice_id>/pay-online/", views.pay_online, name="pay_online"),
    path("billing/<int:invoice_id>/void/", views.invoice_void, name="invoice_void"),
]
