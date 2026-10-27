import time
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, doctor_required, ops_required, patient_required
from appointments.models import Appointment
from billing.models import Invoice, Payment
from clinic.models import DoctorProfile, PatientProfile, Specialty
from clinic.utils import doctor_rows
from records.models import Consultation, LabReport

from .forms import StaffCreateForm

User = get_user_model()


def home(request):
    doctors = doctor_rows(DoctorProfile.objects.select_related("user", "specialty").filter(user__is_active=True)[:6])
    stats = {
        "doctors": DoctorProfile.objects.filter(user__is_active=True).count(),
        "specialties": Specialty.objects.filter(doctors__isnull=False).distinct().count(),
        "patients": User.objects.filter(role="patient").count(),
    }
    return render(request, "home.html", {"doctors": doctors, "stats": stats, "specialties": Specialty.objects.filter(doctors__isnull=False).distinct()})


@login_required
def dashboard(request):
    user = request.user
    target = {"patient": "patient_dashboard", "doctor": "doctor_dashboard", "staff": "desk_dashboard", "admin": "panel"}[user.role]
    return redirect(target)


# --------------------------------------------------------------------------- patient
@patient_required
def patient_dashboard(request):
    user = request.user
    today = timezone.localdate()
    upcoming = list(Appointment.objects.filter(patient=user, date__gte=today, status="scheduled")
                    .select_related("doctor__user", "doctor__specialty").order_by("date", "start_time")[:5])
    invoices = [i for i in Invoice.objects.filter(patient=user).prefetch_related("items", "payments") if i.status in ("unpaid", "partial")]
    context = {
        "next_appointment": upcoming[0] if upcoming else None,
        "upcoming": upcoming,
        "consultations": Consultation.objects.filter(appointment__patient=user).select_related("appointment__doctor__user")[:4],
        "reports": LabReport.objects.filter(patient=user)[:4],
        "due_invoices": invoices,
        "due_total": sum((i.balance for i in invoices), Decimal("0")),
        "profile_incomplete": not PatientProfile.objects.filter(user=user).exclude(date_of_birth=None).exists(),
        "visits": Appointment.objects.filter(patient=user, status="completed").count(),
    }
    return render(request, "dashboard/patient.html", context)


# --------------------------------------------------------------------------- doctor
@doctor_required
def doctor_dashboard(request):
    doctor = get_object_or_404(DoctorProfile, user=request.user)
    today = timezone.localdate()
    todays = Appointment.objects.filter(doctor=doctor, date=today).exclude(status="cancelled").select_related("patient").order_by("start_time")
    month_start = today.replace(day=1)
    context = {
        "doctor": doctor,
        "todays": todays,
        "waiting": todays.filter(status="scheduled").count(),
        "done_today": todays.filter(status="completed").count(),
        "tomorrow": Appointment.objects.filter(doctor=doctor, date=today + timedelta(days=1), status="scheduled").count(),
        "month_completed": Appointment.objects.filter(doctor=doctor, status="completed", date__gte=month_start).count(),
        "patients": User.objects.filter(role="patient", appointments__doctor=doctor).distinct().count(),
        "upcoming": Appointment.objects.filter(doctor=doctor, date__gt=today, status="scheduled").select_related("patient").order_by("date", "start_time")[:6],
    }
    return render(request, "dashboard/doctor.html", context)


# --------------------------------------------------------------------------- front desk
@ops_required
def desk_dashboard(request):
    today = timezone.localdate()
    todays = Appointment.objects.filter(date=today).select_related("patient", "doctor__user").order_by("start_time")
    to_bill = Appointment.objects.filter(status="completed", invoice__isnull=True).select_related("patient", "doctor__user").order_by("-date")[:8]
    open_invoices = [i for i in Invoice.objects.prefetch_related("items", "payments").select_related("patient")[:200] if i.status in ("unpaid", "partial")]
    collected = Payment.objects.filter(paid_at__date=today).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    return render(request, "dashboard/desk.html", {
        "todays": todays, "to_bill": to_bill, "open_invoices": open_invoices[:8],
        "outstanding": sum((i.balance for i in open_invoices), Decimal("0")), "collected": collected,
        "waiting": todays.filter(status="scheduled").count(),
    })


# --------------------------------------------------------------------------- admin panel
@admin_required
def panel(request):
    today = timezone.localdate()
    six_months_ago = (today.replace(day=1) - timedelta(days=150)).replace(day=1)
    revenue = (Payment.objects.filter(paid_at__date__gte=six_months_ago)
               .annotate(m=TruncMonth("paid_at")).values("m").annotate(total=Sum("amount")).order_by("m"))
    revenue = [(r["m"].strftime("%b %Y"), r["total"]) for r in revenue]
    top = max([float(v) for _, v in revenue] or [1]) or 1
    status_counts = {r["status"]: r["n"] for r in Appointment.objects.values("status").annotate(n=Count("id"))}
    total_appts = sum(status_counts.values()) or 1
    busiest = DoctorProfile.objects.annotate(n=Count("appointments")).select_related("user").order_by("-n")[:5]
    busiest_top = max([d.n for d in busiest] or [1]) or 1
    open_invoices = [i for i in Invoice.objects.prefetch_related("items", "payments")[:500] if i.status in ("unpaid", "partial")]
    context = {
        "totals": {
            "patients": User.objects.filter(role="patient").count(),
            "doctors": DoctorProfile.objects.count(),
            "appointments": sum(status_counts.values()),
            "revenue": Payment.objects.aggregate(t=Sum("amount"))["t"] or Decimal("0"),
            "outstanding": sum((i.balance for i in open_invoices), Decimal("0")),
            "today": Appointment.objects.filter(date=today).exclude(status="cancelled").count(),
        },
        "revenue": [(label, value, round(float(value) * 100 / top)) for label, value in revenue],
        "statuses": [(label, status_counts.get(key, 0), round(status_counts.get(key, 0) * 100 / total_appts))
                     for key, label in Appointment.Status.choices],
        "busiest": [(d, d.n, round(d.n * 100 / busiest_top)) for d in busiest],
    }
    return render(request, "dashboard/panel.html", context)


@admin_required
def panel_users(request):
    users = User.objects.all().order_by("-date_joined")
    role = request.GET.get("role", "")
    q = request.GET.get("q", "").strip()
    if role:
        users = users.filter(role=role)
    if q:
        users = users.filter(username__icontains=q) | users.filter(last_name__icontains=q) | users.filter(first_name__icontains=q)
    return render(request, "dashboard/users.html", {"users": users[:200], "role": role, "q": q, "roles": User.Role.choices})


@admin_required
def panel_user_create(request):
    form = StaffCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(username=d["username"], password=d["password"], first_name=d["first_name"],
                                        last_name=d["last_name"], email=d["email"], phone=d["phone"], role=d["role"])
        if d["role"] == "admin":
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        if d["role"] == "doctor":
            specialty, _ = Specialty.objects.get_or_create(name=d["specialty"].strip().title())
            DoctorProfile.objects.create(user=user, specialty=specialty, room=d["room"],
                                         consultation_fee=d["consultation_fee"] if d["consultation_fee"] is not None else Decimal("50"))
            messages.success(request, f"Doctor account created. Now add working hours so patients can book.")
            return redirect("schedule_manage", doctor_id=user.doctor_profile.id)
        messages.success(request, f"{user.get_role_display()} account created for {user.display_name}.")
        return redirect("panel_users")
    return render(request, "dashboard/user_form.html", {"form": form})


@admin_required
@require_POST
def panel_user_update(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot change your own role or status.")
        return redirect("panel_users")
    action = request.POST.get("action")
    if action == "toggle_active":
        target.is_active = not target.is_active
        target.save()
        messages.success(request, f"{target.username} {'enabled' if target.is_active else 'disabled'}.")
    return redirect("panel_users")


@admin_required
def panel_system(request):
    """Shows which database and storage this running copy really uses, with live tests."""
    db = settings.DATABASES["default"]
    info = {
        "db_engine": "PostgreSQL (Amazon RDS)" if "postgresql" in db["ENGINE"] else "SQLite (local file)",
        "db_host": db.get("HOST") or "local file",
        "db_name": str(db["NAME"]),
        "storage_backend": "Amazon S3" if settings.USE_S3 else "Local disk (/media)",
        "bucket": settings.AWS_STORAGE_BUCKET_NAME if settings.USE_S3 else "not used",
        "region": settings.AWS_S3_REGION_NAME if settings.USE_S3 else "not used",
        "timezone": settings.TIME_ZONE,
    }
    try:
        started = time.perf_counter()
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()" if connection.vendor == "postgresql" else "SELECT sqlite_version()")
            version = cursor.fetchone()[0]
        db_result = {"ok": True, "detail": version, "ms": round((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        db_result = {"ok": False, "detail": str(exc), "ms": 0}
    counts = {
        "lab_reports": LabReport.objects.count(),
        "avatars": User.objects.exclude(avatar="").count(),
        "patients": User.objects.filter(role="patient").count(),
        "appointments": Appointment.objects.count(),
    }
    return render(request, "dashboard/system.html", {"info": info, "db_result": db_result, "counts": counts,
                                                     "s3_result": request.session.pop("s3_test", None)})


@admin_required
@require_POST
def panel_s3_test(request):
    name = f"healthcheck/test-{int(time.time())}.txt"
    payload = f"CareDesk storage test at {timezone.now().isoformat()}".encode()
    try:
        saved = default_storage.save(name, ContentFile(payload))
        with default_storage.open(saved, "rb") as fh:
            same = fh.read() == payload
        url = default_storage.url(saved)
        default_storage.delete(saved)
        result = {"ok": same, "detail": f"Wrote, read back and deleted {saved}.", "url": url.split("?")[0]}
    except Exception as exc:
        result = {"ok": False, "detail": f"{type(exc).__name__}: {exc}", "url": ""}
    request.session["s3_test"] = result
    return redirect("panel_system")


def health(request):
    """For the Beanstalk load balancer and quick checks. No login needed."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HttpResponse("ok", content_type="text/plain")
    except Exception:
        return HttpResponse("database unavailable", status=503, content_type="text/plain")


def error_403(request, exception=None):
    return render(request, "403.html", status=403)


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
