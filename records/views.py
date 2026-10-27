from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import clinical_required
from appointments.models import Appointment
from clinic.permissions import can_view_clinical, patients_of_doctor

from .forms import ConsultationForm, LabReportForm, PrescriptionForm
from .models import Consultation, LabReport, Prescription

User = get_user_model()


def _own_appointment(request, appointment_id):
    appt = get_object_or_404(Appointment.objects.select_related("patient", "doctor__user"), pk=appointment_id)
    if not (request.user.is_clinic_admin or appt.doctor.user_id == request.user.id):
        raise PermissionDenied
    return appt


@clinical_required
def consult(request, appointment_id):
    appt = _own_appointment(request, appointment_id)
    if appt.status in ("cancelled", "no_show"):
        messages.error(request, "This appointment was cancelled or missed, so it cannot be consulted.")
        return redirect("appointment_detail", appointment_id=appt.id)
    instance = getattr(appt, "consultation", None)
    form = ConsultationForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        consultation = form.save(commit=False)
        consultation.appointment = appt
        consultation.save()
        if appt.status != "completed":
            appt.status = Appointment.Status.COMPLETED
            appt.save(update_fields=["status"])
        messages.success(request, "Consultation saved. The appointment is marked as completed.")
        return redirect("consult", appointment_id=appt.id)
    profile = getattr(appt.patient, "patient_profile", None)
    previous = Consultation.objects.filter(appointment__patient=appt.patient).exclude(appointment=appt)[:3]
    return render(request, "records/consult.html", {
        "appt": appt, "form": form, "consultation": instance, "profile": profile,
        "rx_form": PrescriptionForm(), "previous": previous,
    })


@clinical_required
@require_POST
def prescription_add(request, appointment_id):
    appt = _own_appointment(request, appointment_id)
    consultation = get_object_or_404(Consultation, appointment=appt)
    form = PrescriptionForm(request.POST)
    if form.is_valid():
        rx = form.save(commit=False)
        rx.consultation = consultation
        rx.save()
        messages.success(request, f"Added {rx.medicine}.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("consult", appointment_id=appt.id)


@clinical_required
@require_POST
def prescription_delete(request, appointment_id, prescription_id):
    appt = _own_appointment(request, appointment_id)
    get_object_or_404(Prescription, pk=prescription_id, consultation__appointment=appt).delete()
    messages.success(request, "Medicine removed.")
    return redirect("consult", appointment_id=appt.id)


@login_required
def consultation_detail(request, consultation_id):
    consultation = get_object_or_404(
        Consultation.objects.select_related("appointment__patient", "appointment__doctor__user", "appointment__doctor__specialty"),
        pk=consultation_id,
    )
    appt = consultation.appointment
    if not (request.user.is_clinic_admin or request.user.id == appt.patient_id or request.user.id == appt.doctor.user_id):
        raise PermissionDenied
    return render(request, "records/consultation_detail.html", {
        "c": consultation, "appt": appt, "profile": getattr(appt.patient, "patient_profile", None),
    })


@login_required
def my_records(request):
    """A patient's own visit history."""
    if not request.user.is_patient:
        raise PermissionDenied
    consultations = Consultation.objects.filter(appointment__patient=request.user).select_related(
        "appointment__doctor__user", "appointment__doctor__specialty"
    ).prefetch_related("prescriptions")
    return render(request, "records/my_records.html", {"consultations": consultations})


# ---------------------------------------------------------------- lab reports
@login_required
def report_list(request):
    user = request.user
    if user.runs_operations and not user.is_clinic_admin:
        raise PermissionDenied  # front desk never sees clinical files
    patient = user
    if not user.is_patient:
        pid = request.GET.get("patient")
        patient = get_object_or_404(User, pk=pid, role="patient") if pid else None
        if patient and not can_view_clinical(user, patient):
            raise PermissionDenied
    if patient is None:
        qs = LabReport.objects.all() if user.is_clinic_admin else LabReport.objects.filter(patient__in=patients_of_doctor(user))
    else:
        qs = LabReport.objects.filter(patient=patient)
    return render(request, "records/report_list.html", {"reports": qs.select_related("patient", "uploaded_by")[:200], "patient": patient})


@login_required
def report_upload(request):
    user = request.user
    if user.runs_operations and not user.is_clinic_admin:
        raise PermissionDenied
    patient = user
    if not user.is_patient:
        patient = get_object_or_404(User, pk=request.GET.get("patient") or request.POST.get("patient"), role="patient")
        if not can_view_clinical(user, patient):
            raise PermissionDenied
    form = LabReportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.patient = patient
        report.uploaded_by = user
        report.save()
        messages.success(request, "Lab report uploaded.")
        if user.is_patient:
            return redirect("report_list")
        return redirect(f"/reports/?patient={patient.id}")
    return render(request, "records/report_form.html", {"form": form, "patient": patient})


@login_required
def report_download(request, report_id):
    """Checks permission, then redirects to the file (a short-lived signed S3 link on AWS)."""
    report = get_object_or_404(LabReport.objects.select_related("patient"), pk=report_id)
    if not can_view_clinical(request.user, report.patient):
        raise PermissionDenied
    return redirect(report.file.url)


@login_required
@require_POST
def report_delete(request, report_id):
    report = get_object_or_404(LabReport, pk=report_id)
    if not (request.user.is_clinic_admin or report.uploaded_by_id == request.user.id):
        raise PermissionDenied
    patient_id = report.patient_id
    report.delete()
    messages.success(request, "Report deleted.")
    return redirect("report_list") if request.user.is_patient else redirect(f"/reports/?patient={patient_id}")
