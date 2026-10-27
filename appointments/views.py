from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from clinic.models import DoctorProfile

from .models import Appointment
from .services import MAX_DAYS_AHEAD, available_slots

User = get_user_model()


def _parse_date(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@login_required
def book(request):
    user = request.user
    if user.is_doctor:
        raise PermissionDenied
    doctors = DoctorProfile.objects.select_related("user", "specialty").filter(user__is_active=True)
    params = request.POST if request.method == "POST" else request.GET
    doctor = doctors.filter(pk=params.get("doctor")).first() if params.get("doctor") else None
    day = _parse_date(params.get("date"))
    today = timezone.localdate()

    patient = user
    patients = None
    if user.runs_operations:
        patients = User.objects.filter(role="patient", is_active=True).order_by("first_name", "username")
        patient = patients.filter(pk=params.get("patient")).first() if params.get("patient") else None

    slots = available_slots(doctor, day) if doctor and day else []

    if request.method == "POST":
        start_raw = request.POST.get("slot", "")
        chosen = next(((s, e) for s, e in slots if s.strftime("%H:%M") == start_raw), None)
        if not doctor or not day:
            messages.error(request, "Choose a doctor and a date first.")
        elif patient is None:
            messages.error(request, "Choose which patient this appointment is for.")
        elif chosen is None:
            messages.error(request, "That time is no longer available. Pick another slot.")
        else:
            try:
                with transaction.atomic():
                    appt = Appointment.objects.create(
                        patient=patient, doctor=doctor, date=day, start_time=chosen[0], end_time=chosen[1],
                        reason=request.POST.get("reason", "").strip()[:240], created_by=user,
                    )
            except IntegrityError:
                messages.error(request, "Someone just booked that slot. Please choose another.")
            else:
                messages.success(request, f"Appointment booked with {doctor.name} on {day:%A %d %B} at {chosen[0]:%H:%M}.")
                return redirect("appointment_detail", appointment_id=appt.id)

    context = {
        "doctors": doctors, "doctor": doctor, "day": day, "slots": slots, "patients": patients, "patient": patient,
        "min_date": today, "max_date": today + timedelta(days=MAX_DAYS_AHEAD),
        "default_date": (today + timedelta(days=1)).isoformat(),
    }
    return render(request, "appointments/book.html", context)


@login_required
def appointment_list(request):
    user = request.user
    qs = Appointment.objects.select_related("patient", "doctor__user", "doctor__specialty")
    if user.is_patient:
        qs = qs.filter(patient=user)
    elif user.is_doctor:
        qs = qs.filter(doctor__user=user)
    when = request.GET.get("when", "upcoming")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    today = timezone.localdate()
    if when == "today":
        qs = qs.filter(date=today)
    elif when == "upcoming":
        qs = qs.filter(date__gte=today).exclude(status__in=["cancelled", "no_show"])
    elif when == "past":
        qs = qs.filter(date__lt=today)
    if status:
        qs = qs.filter(status=status)
    if q and not user.is_patient:
        qs = qs.filter(Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q) | Q(patient__username__icontains=q))
    ordering = ("-date", "-start_time") if when == "past" else ("date", "start_time")
    return render(request, "appointments/list.html", {
        "appointments": qs.order_by(*ordering)[:300], "when": when, "status": status, "q": q,
        "statuses": Appointment.Status.choices,
    })


def _can_see(user, appt):
    return (user.runs_operations or appt.patient_id == user.id or appt.doctor.user_id == user.id)


@login_required
def appointment_detail(request, appointment_id):
    appt = get_object_or_404(Appointment.objects.select_related("patient", "doctor__user", "doctor__specialty"), pk=appointment_id)
    if not _can_see(request.user, appt):
        raise PermissionDenied
    consultation = getattr(appt, "consultation", None)
    invoice = getattr(appt, "invoice", None)
    user = request.user
    context = {
        "appt": appt, "consultation": consultation, "invoice": invoice,
        "can_consult": appt.doctor.user_id == user.id or user.is_clinic_admin,
        "can_cancel": appt.can_cancel and (user.runs_operations or appt.patient_id == user.id),
        "can_mark_no_show": appt.status == "scheduled" and (user.runs_operations or appt.doctor.user_id == user.id),
        "can_invoice": user.runs_operations and appt.status == "completed" and invoice is None,
        "can_see_clinical": consultation and (user.is_clinic_admin or user.id == appt.patient_id or appt.doctor.user_id == user.id),
    }
    return render(request, "appointments/detail.html", context)


@login_required
@require_POST
def appointment_cancel(request, appointment_id):
    appt = get_object_or_404(Appointment, pk=appointment_id)
    if not (request.user.runs_operations or appt.patient_id == request.user.id):
        raise PermissionDenied
    if not appt.can_cancel:
        messages.error(request, "Only upcoming scheduled appointments can be cancelled.")
    else:
        appt.status = Appointment.Status.CANCELLED
        appt.save(update_fields=["status"])
        messages.success(request, "Appointment cancelled. The time slot is open again.")
    return redirect("appointment_detail", appointment_id=appt.id)


@login_required
@require_POST
def appointment_no_show(request, appointment_id):
    appt = get_object_or_404(Appointment.objects.select_related("doctor"), pk=appointment_id)
    if not (request.user.runs_operations or appt.doctor.user_id == request.user.id):
        raise PermissionDenied
    if appt.status == "scheduled":
        appt.status = Appointment.Status.NO_SHOW
        appt.save(update_fields=["status"])
        messages.success(request, "Marked as no show.")
    return redirect("appointment_detail", appointment_id=appt.id)
