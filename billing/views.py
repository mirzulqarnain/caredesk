from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import ops_required
from appointments.models import Appointment

from .forms import InvoiceCreateForm, ItemForm, PaymentForm
from .models import Invoice, InvoiceItem, Payment


def _invoices():
    return Invoice.objects.select_related("patient", "appointment__doctor__user").prefetch_related("items", "payments")


def _can_view(user, invoice):
    return user.runs_operations or invoice.patient_id == user.id


@login_required
def invoice_list(request):
    user = request.user
    if user.is_doctor:
        raise PermissionDenied
    qs = _invoices()
    if user.is_patient:
        qs = qs.filter(patient=user)
    q = request.GET.get("q", "").strip()
    if q and not user.is_patient:
        qs = qs.filter(Q(number__icontains=q) | Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q) | Q(patient__username__icontains=q))
    status = request.GET.get("status", "")
    invoices = list(qs[:300])
    if status:
        invoices = [i for i in invoices if i.status == status]
    outstanding = sum((i.balance for i in invoices if i.status in ("unpaid", "partial")), Decimal("0"))
    return render(request, "billing/list.html", {
        "invoices": invoices, "q": q, "status": status, "outstanding": outstanding,
        "statuses": ["unpaid", "partial", "paid", "draft", "void"],
    })


@ops_required
def invoice_create(request):
    form = InvoiceCreateForm(request.POST or None, initial={"patient": request.GET.get("patient")})
    if request.method == "POST" and form.is_valid():
        invoice = Invoice.objects.create(patient=form.cleaned_data["patient"], notes=form.cleaned_data["notes"], created_by=request.user)
        messages.success(request, "Invoice created. Add the charges below.")
        return redirect("invoice_detail", invoice_id=invoice.id)
    return render(request, "billing/create.html", {"form": form})


@ops_required
@require_POST
def invoice_from_appointment(request, appointment_id):
    appt = get_object_or_404(Appointment.objects.select_related("doctor__user", "patient"), pk=appointment_id)
    if appt.status != "completed":
        messages.error(request, "Only completed appointments can be billed.")
        return redirect("appointment_detail", appointment_id=appt.id)
    existing = Invoice.objects.filter(appointment=appt).first()
    if existing:
        return redirect("invoice_detail", invoice_id=existing.id)
    invoice = Invoice.objects.create(patient=appt.patient, appointment=appt, created_by=request.user,
                                     notes=f"Visit on {appt.date:%d %b %Y}")
    InvoiceItem.objects.create(invoice=invoice, description=f"Consultation with {appt.doctor.name}", quantity=1,
                               unit_price=appt.doctor.consultation_fee)
    messages.success(request, "Invoice created with the consultation fee. Add any extra charges below.")
    return redirect("invoice_detail", invoice_id=invoice.id)


@login_required
def invoice_detail(request, invoice_id):
    invoice = get_object_or_404(_invoices(), pk=invoice_id)
    if not _can_view(request.user, invoice):
        raise PermissionDenied
    ops = request.user.runs_operations
    return render(request, "billing/detail.html", {
        "invoice": invoice, "ops": ops,
        "item_form": ItemForm() if ops and invoice.can_edit_items else None,
        "payment_form": PaymentForm(balance=invoice.balance) if ops and not invoice.is_void and invoice.balance > 0 else None,
        "can_pay_online": request.user.is_patient and not invoice.is_void and invoice.balance > 0,
    })


@ops_required
@require_POST
def item_add(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    if not invoice.can_edit_items:
        messages.error(request, "Charges cannot change after a payment or once the invoice is void.")
        return redirect("invoice_detail", invoice_id=invoice.id)
    form = ItemForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.invoice = invoice
        item.save()
        messages.success(request, "Charge added.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("invoice_detail", invoice_id=invoice.id)


@ops_required
@require_POST
def item_delete(request, invoice_id, item_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    if invoice.can_edit_items:
        get_object_or_404(InvoiceItem, pk=item_id, invoice=invoice).delete()
        messages.success(request, "Charge removed.")
    else:
        messages.error(request, "Charges cannot change after a payment or once the invoice is void.")
    return redirect("invoice_detail", invoice_id=invoice.id)


@ops_required
@require_POST
def payment_add(request, invoice_id):
    invoice = get_object_or_404(_invoices(), pk=invoice_id)
    if invoice.is_void or invoice.balance <= 0:
        messages.error(request, "Nothing is due on this invoice.")
        return redirect("invoice_detail", invoice_id=invoice.id)
    form = PaymentForm(request.POST, balance=invoice.balance)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.received_by = request.user
        payment.save()
        messages.success(request, f"Payment of {payment.amount} recorded.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("invoice_detail", invoice_id=invoice.id)


@login_required
@require_POST
def pay_online(request, invoice_id):
    """Simulated online payment: no gateway, it simply records a payment for the full balance."""
    invoice = get_object_or_404(_invoices(), pk=invoice_id, patient=request.user)
    if invoice.is_void or invoice.balance <= 0:
        messages.error(request, "Nothing is due on this invoice.")
    else:
        Payment.objects.create(invoice=invoice, amount=invoice.balance, method="online", received_by=request.user,
                               reference=f"SIM-{int(timezone.now().timestamp())}")
        messages.success(request, "Payment received. This is a simulated online payment, no real money moved.")
    return redirect("invoice_detail", invoice_id=invoice.id)


@ops_required
@require_POST
def invoice_void(request, invoice_id):
    invoice = get_object_or_404(_invoices(), pk=invoice_id)
    if invoice.payments.exists():
        messages.error(request, "An invoice with payments cannot be voided.")
    else:
        invoice.is_void = True
        invoice.save(update_fields=["is_void"])
        messages.success(request, "Invoice voided.")
    return redirect("invoice_detail", invoice_id=invoice.id)
