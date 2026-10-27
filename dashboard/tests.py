"""End to end checks of every module. Run with:  python manage.py test"""
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import available_slots
from billing.models import Invoice, Payment
from clinic.models import DoctorProfile, Schedule
from records.models import Consultation, LabReport, Prescription

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp()


def next_weekday(start_offset=1):
    """First date from tomorrow that is Monday to Friday (Dr Amina works those days)."""
    day = timezone.localdate() + timedelta(days=start_offset)
    while day.weekday() > 4:
        day += timedelta(days=1)
    return day


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class ClinicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def login(self, username, password):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=password))

    @property
    def amina(self):
        return DoctorProfile.objects.get(user__username="dr_amina")

    # ---------------------------------------------------------------- public and auth
    def test_public_pages_and_health(self):
        for name in ("home", "doctors", "login", "register", "health"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("doctor_detail", args=[self.amina.id])).status_code, 200)

    def test_register_makes_patient_only(self):
        resp = self.client.post(reverse("register"), {
            "username": "newpat", "first_name": "New", "last_name": "Pat", "email": "np@x.com", "phone": "1",
            "password1": "S3cretpass!", "password2": "S3cretpass!", "role": "admin",
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="newpat")
        self.assertEqual(user.role, "patient")
        self.assertTrue(hasattr(user, "patient_profile"))

    def test_every_role_reaches_its_dashboard(self):
        expected = {"pat_zara": "patient_dashboard", "dr_amina": "doctor_dashboard", "desk": "desk_dashboard", "clinic_admin": "panel"}
        passwords = {"pat_zara": "patient123", "dr_amina": "doctor123", "desk": "desk123", "clinic_admin": "admin123"}
        for username, target in expected.items():
            self.login(username, passwords[username])
            resp = self.client.get(reverse("dashboard"))
            self.assertRedirects(resp, reverse(target), fetch_redirect_response=False)
            self.assertEqual(self.client.get(reverse(target)).status_code, 200, target)

    def test_role_protection(self):
        self.login("pat_zara", "patient123")
        for name in ("panel", "desk_dashboard", "patients", "doctor_dashboard"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.login("desk", "desk123")
        self.assertEqual(self.client.get(reverse("panel")).status_code, 403)

    def test_profile_saves_health_details(self):
        self.login("pat_omar", "patient123")
        resp = self.client.post(reverse("profile"), {
            "a-first_name": "Omar", "a-last_name": "Ahmed", "a-email": "o@x.com", "a-phone": "123",
            "p-date_of_birth": "1990-01-01", "p-gender": "male", "p-blood_group": "B+", "p-allergies": "Dust",
            "p-emergency_contact": "Sam", "p-address": "Street 1",
        })
        self.assertEqual(resp.status_code, 302)
        profile = User.objects.get(username="pat_omar").patient_profile
        self.assertEqual((profile.blood_group, profile.allergies), ("B+", "Dust"))

    # ---------------------------------------------------------------- booking
    def test_slots_and_booking_flow(self):
        day = next_weekday()
        slots = available_slots(self.amina, day)
        self.assertEqual(len(slots), 8)  # 09:00 to 13:00 in 30 minute visits
        self.login("pat_omar", "patient123")
        page = self.client.get(reverse("book"), {"doctor": self.amina.id, "date": day.isoformat()})
        self.assertContains(page, "09:00")
        resp = self.client.post(reverse("book"), {"doctor": self.amina.id, "date": day.isoformat(), "slot": "09:00", "reason": "Checkup"})
        appt = Appointment.objects.get(patient__username="pat_omar", date=day)
        self.assertRedirects(resp, reverse("appointment_detail", args=[appt.id]), fetch_redirect_response=False)
        self.assertEqual(len(available_slots(self.amina, day)), 7)

        # a second patient cannot take the same slot
        self.login("pat_zara", "patient123")
        self.client.post(reverse("book"), {"doctor": self.amina.id, "date": day.isoformat(), "slot": "09:00"})
        self.assertEqual(Appointment.objects.filter(doctor=self.amina, date=day, start_time="09:00").count(), 1)

        # cancelling frees it again
        self.login("pat_omar", "patient123")
        self.client.post(reverse("appointment_cancel", args=[appt.id]))
        appt.refresh_from_db()
        self.assertEqual(appt.status, "cancelled")
        self.assertEqual(len(available_slots(self.amina, day)), 8)

    def test_cannot_book_past_or_non_working_day(self):
        past = timezone.localdate() - timedelta(days=1)
        self.assertEqual(available_slots(self.amina, past), [])
        saturday = next_weekday() + timedelta(days=(5 - next_weekday().weekday()))
        self.assertEqual(available_slots(self.amina, saturday), [])
        far = timezone.localdate() + timedelta(days=200)
        self.assertEqual(available_slots(self.amina, far), [])

    def test_front_desk_registers_and_books_for_patient(self):
        self.login("desk", "desk123")
        resp = self.client.post(reverse("patient_create"), {
            "username": "walkin", "first_name": "Walk", "last_name": "In", "phone": "555", "password": "walkin123",
        })
        walkin = User.objects.get(username="walkin")
        self.assertEqual(walkin.role, "patient")
        self.assertRedirects(resp, f"/appointments/book/?patient={walkin.id}", fetch_redirect_response=False)
        day = next_weekday()
        self.client.post(reverse("book"), {"patient": walkin.id, "doctor": self.amina.id, "date": day.isoformat(), "slot": "10:00"})
        self.assertTrue(Appointment.objects.filter(patient=walkin, date=day).exists())

    def test_doctor_cannot_book(self):
        self.login("dr_amina", "doctor123")
        self.assertEqual(self.client.get(reverse("book")).status_code, 403)

    # ---------------------------------------------------------------- consultation and privacy
    def test_consultation_prescription_and_privacy(self):
        omar = User.objects.get(username="pat_omar")
        appt = Appointment.objects.get(patient=omar, date=timezone.localdate(), start_time="16:00")
        self.login("dr_amina", "doctor123")
        self.assertEqual(self.client.get(reverse("consult", args=[appt.id])).status_code, 200)
        resp = self.client.post(reverse("consult", args=[appt.id]), {
            "symptoms": "Pain", "diagnosis": "Recovering strain", "notes": "Continue stretching", "blood_pressure": "120/80",
            "pulse": "70", "temperature": "36.8", "weight_kg": "80.5", "follow_up_date": "",
        })
        self.assertRedirects(resp, reverse("consult", args=[appt.id]), fetch_redirect_response=False)
        appt.refresh_from_db()
        self.assertEqual(appt.status, "completed")
        self.client.post(reverse("prescription_add", args=[appt.id]), {
            "medicine": "Paracetamol", "dosage": "500 mg", "frequency": "Twice a day", "duration_days": "3", "instructions": ""})
        consultation = Consultation.objects.get(appointment=appt)
        self.assertEqual(consultation.prescriptions.count(), 1)
        rx = consultation.prescriptions.get()
        self.client.post(reverse("prescription_delete", args=[appt.id, rx.id]))
        self.assertEqual(consultation.prescriptions.count(), 0)

        url = reverse("consultation_detail", args=[consultation.id])
        for username, password, code in (("pat_omar", "patient123", 200), ("clinic_admin", "admin123", 200),
                                         ("pat_zara", "patient123", 403), ("desk", "desk123", 403), ("dr_bilal", "doctor123", 403)):
            self.login(username, password)
            self.assertEqual(self.client.get(url).status_code, code, username)

        # another doctor cannot consult someone else's appointment
        self.login("dr_bilal", "doctor123")
        self.assertEqual(self.client.get(reverse("consult", args=[appt.id])).status_code, 403)

    def test_front_desk_cannot_see_clinical_data(self):
        zara = User.objects.get(username="pat_zara")
        self.login("desk", "desk123")
        page = self.client.get(reverse("patient_detail", args=[zara.id]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Acute bronchitis")
        self.assertEqual(self.client.get(reverse("report_list")).status_code, 403)
        report = LabReport.objects.get()
        self.assertEqual(self.client.get(reverse("report_download", args=[report.id])).status_code, 403)

    def test_doctor_sees_only_own_patients(self):
        self.login("dr_chen", "doctor123")  # has no appointments
        self.assertNotContains(self.client.get(reverse("patients")), "Zara")
        zara = User.objects.get(username="pat_zara")
        self.assertEqual(self.client.get(reverse("patient_detail", args=[zara.id])).status_code, 403)
        self.login("dr_amina", "doctor123")
        self.assertContains(self.client.get(reverse("patients")), "Zara")

    # ---------------------------------------------------------------- lab reports
    def test_lab_report_upload_download_and_validation(self):
        self.login("pat_omar", "patient123")
        good = SimpleUploadedFile("scan.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        resp = self.client.post(reverse("report_upload"), {"title": "Chest X-ray", "report_type": "imaging", "notes": "", "file": good})
        self.assertRedirects(resp, reverse("report_list"), fetch_redirect_response=False)
        report = LabReport.objects.get(title="Chest X-ray")
        self.assertTrue(report.file.name.startswith("lab_reports/"))
        resp = self.client.get(reverse("report_download", args=[report.id]))
        self.assertEqual(resp.status_code, 302)
        bad = SimpleUploadedFile("run.exe", b"MZ")
        self.client.post(reverse("report_upload"), {"title": "Bad", "report_type": "other", "file": bad})
        self.assertFalse(LabReport.objects.filter(title="Bad").exists())
        self.login("pat_zara", "patient123")
        self.assertEqual(self.client.get(reverse("report_download", args=[report.id])).status_code, 403)

    # ---------------------------------------------------------------- billing
    def test_invoice_from_appointment_and_payments(self):
        omar = User.objects.get(username="pat_omar")
        done = Appointment.objects.get(patient=omar, status="completed")
        self.login("desk", "desk123")
        self.client.post(reverse("invoice_from_appointment", args=[done.id]))
        invoice = Invoice.objects.get(appointment=done)
        self.assertEqual(invoice.total, Decimal("40.00"))
        self.assertEqual(invoice.status, "unpaid")
        self.client.post(reverse("item_add", args=[invoice.id]), {"description": "Dressing", "quantity": "2", "unit_price": "5.00"})
        self.assertEqual(invoice.total, Decimal("50.00"))
        # over payment is rejected, partial and full accepted
        self.client.post(reverse("payment_add", args=[invoice.id]), {"amount": "500", "method": "cash"})
        self.assertEqual(invoice.payments.count(), 0)
        self.client.post(reverse("payment_add", args=[invoice.id]), {"amount": "20", "method": "cash"})
        invoice = Invoice.objects.get(pk=invoice.pk)
        self.assertEqual(invoice.status, "partial")
        self.assertEqual(invoice.balance, Decimal("30.00"))
        # charges are locked after a payment
        self.client.post(reverse("item_add", args=[invoice.id]), {"description": "Late", "quantity": "1", "unit_price": "9"})
        self.assertEqual(invoice.items.count(), 2)
        # patient pays the rest online (simulated)
        self.login("pat_omar", "patient123")
        self.client.post(reverse("pay_online", args=[invoice.id]))
        invoice = Invoice.objects.get(pk=invoice.pk)
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(invoice.payments.filter(method="online").count(), 1)
        # other patients cannot open it
        self.login("pat_zara", "patient123")
        self.assertEqual(self.client.get(reverse("invoice_detail", args=[invoice.id])).status_code, 403)

    def test_void_invoice_and_patient_list(self):
        self.login("desk", "desk123")
        zara = User.objects.get(username="pat_zara")
        self.client.post(reverse("invoice_create"), {"patient": zara.id, "notes": "Test"})
        invoice = Invoice.objects.filter(notes="Test").get()
        self.assertEqual(invoice.status, "draft")
        self.client.post(reverse("invoice_void", args=[invoice.id]))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "void")
        self.login("pat_zara", "patient123")
        self.assertContains(self.client.get(reverse("invoice_list")), "INV-")

    # ---------------------------------------------------------------- admin
    def test_admin_creates_doctor_who_sets_hours(self):
        self.login("clinic_admin", "admin123")
        resp = self.client.post(reverse("panel_user_create"), {
            "username": "dr_new", "first_name": "Nadia", "last_name": "Iqbal", "email": "n@x.com", "phone": "1",
            "role": "doctor", "password": "doctor123", "specialty": "cardiology", "consultation_fee": "75", "room": "Room 9",
        })
        doctor = DoctorProfile.objects.get(user__username="dr_new")
        self.assertRedirects(resp, reverse("schedule_manage", args=[doctor.id]), fetch_redirect_response=False)
        self.assertEqual(doctor.specialty.name, "Cardiology")
        self.login("dr_new", "doctor123")
        self.client.post(reverse("schedule_manage", args=[doctor.id]), {"weekday": "2", "start_time": "09:00", "end_time": "11:00", "slot_minutes": "30"})
        self.assertEqual(doctor.schedules.count(), 1)
        resp = self.client.post(reverse("schedule_manage", args=[doctor.id]), {"weekday": "2", "start_time": "10:00", "end_time": "12:00", "slot_minutes": "30"})
        self.assertContains(resp, "overlaps")
        # doctors cannot edit each other's hours
        self.login("dr_chen", "doctor123")
        self.assertEqual(self.client.get(reverse("schedule_manage", args=[doctor.id])).status_code, 403)

    def test_admin_pages_users_and_storage_test(self):
        self.login("clinic_admin", "admin123")
        for name in ("panel", "panel_users", "panel_user_create", "panel_system"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        zara = User.objects.get(username="pat_zara")
        self.client.post(reverse("panel_user_update", args=[zara.id]), {"action": "toggle_active"})
        zara.refresh_from_db()
        self.assertFalse(zara.is_active)
        self.client.post(reverse("panel_s3_test"))
        page = self.client.get(reverse("panel_system"))
        self.assertContains(page, "Storage works")
        self.assertContains(page, "Connected")

    # ---------------------------------------------------------------- commands
    def test_seed_is_idempotent_and_check_aws_passes(self):
        before = User.objects.count()
        call_command("seed_demo", verbosity=0)
        self.assertEqual(User.objects.count(), before)
        out = StringIO()
        call_command("check_aws", stdout=out)
        self.assertIn("All checks passed", out.getvalue())
