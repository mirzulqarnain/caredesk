from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import ops_required
from appointments.models import Appointment
from billing.models import Invoice
from records.models import Consultation, LabReport

from .forms import PatientCreateForm, ScheduleForm
from .models import DoctorProfile, PatientProfile, Schedule, Specialty
from .utils import doctor_rows
from .permissions import can_view_clinical, can_view_patient, patients_of_doctor

User = get_user_model()


def doctors(request):
    qs = DoctorProfile.objects.select_related("user", "specialty").filter(user__is_active=True).prefetch_related("schedules")
    q = request.GET.get("q", "").strip()
    specialty = request.GET.get("specialty", "")
    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(specialty__name__icontains=q))
    if specialty:
        qs = qs.filter(specialty_id=specialty)
    rows = doctor_rows(qs)
    return render(request, "clinic/doctors.html", {
        "rows": rows, "specialties": Specialty.objects.all(), "q": q, "selected_specialty": specialty,
    })


def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile.objects.select_related("user", "specialty"), pk=doctor_id)
    week = OrderedDict()
    for s in doctor.schedules.all():
        week.setdefault(s.get_weekday_display(), []).append(s)
    return render(request, "clinic/doctor_detail.html", {"doctor": doctor, "week": week})


@login_required
def schedule_manage(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile.objects.select_related("user"), pk=doctor_id)
    if not (request.user.is_clinic_admin or doctor.user_id == request.user.id):
        raise PermissionDenied
    form = ScheduleForm(request.POST or None, doctor=doctor)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.doctor = doctor
        item.save()
        messages.success(request, "Working hours added.")
        return redirect("schedule_manage", doctor_id=doctor.id)
    return render(request, "clinic/schedule.html", {"doctor": doctor, "form": form, "schedules": doctor.schedules.all()})


@login_required
@require_POST
def schedule_delete(request, doctor_id, schedule_id):
    doctor = get_object_or_404(DoctorProfile, pk=doctor_id)
    if not (request.user.is_clinic_admin or doctor.user_id == request.user.id):
        raise PermissionDenied
    get_object_or_404(Schedule, pk=schedule_id, doctor=doctor).delete()
    messages.success(request, "Working hours removed. Existing appointments are not affected.")
    return redirect("schedule_manage", doctor_id=doctor.id)


@login_required
def patients(request):
    user = request.user
    if user.is_patient:
        raise PermissionDenied
    qs = patients_of_doctor(user) if user.is_doctor else User.objects.filter(role="patient")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q) | Q(phone__icontains=q)
        )
    return render(request, "clinic/patients.html", {"patients": qs.select_related("patient_profile").order_by("first_name", "username")[:200], "q": q})


@login_required
def patient_detail(request, user_id):
    patient = get_object_or_404(User, pk=user_id, role="patient")
    if not can_view_patient(request.user, patient):
        raise PermissionDenied
    profile, _ = PatientProfile.objects.get_or_create(user=patient)
    appointments = patient.appointments.select_related("doctor__user", "doctor__specialty").order_by("-date", "-start_time")
    if request.user.is_doctor:
        appointments = appointments.filter(doctor__user=request.user)
    clinical = can_view_clinical(request.user, patient)
    context = {
        "patient": patient, "profile": profile, "appointments": appointments[:15], "clinical": clinical,
        "consultations": Consultation.objects.filter(appointment__patient=patient).select_related("appointment__doctor__user")[:10] if clinical else [],
        "reports": LabReport.objects.filter(patient=patient)[:10] if clinical else [],
        "invoices": Invoice.objects.filter(patient=patient)[:10] if request.user.runs_operations else [],
    }
    return render(request, "clinic/patient_detail.html", context)


@ops_required
def patient_create(request):
    form = PatientCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        patient = User.objects.create_user(
            username=d["username"], password=d["password"], first_name=d["first_name"], last_name=d["last_name"],
            email=d["email"], phone=d["phone"], role="patient",
        )
        profile, _ = PatientProfile.objects.get_or_create(user=patient)
        profile.date_of_birth = d.get("date_of_birth")
        profile.gender = d.get("gender") or ""
        profile.save()
        messages.success(request, f"Registered {patient.display_name}. You can book their first appointment now.")
        return redirect(f"/appointments/book/?patient={patient.id}")
    return render(request, "clinic/patient_form.html", {"form": form})
