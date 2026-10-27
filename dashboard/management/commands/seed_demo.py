"""Create demo doctors, a front desk user, patients, appointments, a consultation, an invoice and a lab report.

    python manage.py seed_demo

All or nothing: it runs in one database transaction, and does nothing if the demo data is already there.
The lab report is uploaded through the normal storage backend, so with USE_S3=True a real object lands in your bucket.
"""
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from billing.models import Invoice, InvoiceItem, Payment
from clinic.models import DoctorProfile, PatientProfile, Schedule, Specialty
from records.models import Consultation, LabReport, Prescription

User = get_user_model()

DOCTORS = [
    ("dr_amina", "Amina", "Rahman", "General Medicine", "Room 1", "40.00", 12,
     "Family doctor focused on prevention, chronic conditions and everyday illness.",
     [(0, 9, 13, 30), (1, 9, 13, 30), (2, 9, 13, 30), (3, 9, 13, 30), (4, 9, 13, 30)]),
    ("dr_bilal", "Bilal", "Siddiqui", "Pediatrics", "Room 2", "45.00", 8,
     "Child health, vaccination and growth checks from newborn to teenager.",
     [(0, 14, 18, 20), (2, 14, 18, 20), (4, 14, 18, 20)]),
    ("dr_chen", "Mei", "Chen", "Dermatology", "Room 3", "60.00", 15,
     "Skin, hair and nail conditions, including acne, eczema and allergies.",
     [(1, 10, 14, 30), (3, 10, 14, 30), (5, 10, 13, 30)]),
]


class Command(BaseCommand):
    help = "Create demo data."

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(username="dr_amina").exists():
            self.stdout.write("Demo data is already present. Nothing to do.")
            return

        self._user("clinic_admin", "Clinic", "Admin", "admin123", "admin", superuser=True)
        self._user("desk", "Hira", "Malik", "desk123", "staff", phone="0300 1112233")
        profiles = {}
        for username, first, last, spec, room, fee, years, bio, hours in DOCTORS:
            user = self._user(username, first, last, "doctor123", "doctor")
            specialty, _ = Specialty.objects.get_or_create(name=spec)
            doc = DoctorProfile.objects.create(user=user, specialty=specialty, room=room, consultation_fee=Decimal(fee),
                                               years_experience=years, bio=bio)
            for weekday, start, end, minutes in hours:
                Schedule.objects.create(doctor=doc, weekday=weekday, start_time=time(start), end_time=time(end), slot_minutes=minutes)
            profiles[username] = doc

        zara = self._user("pat_zara", "Zara", "Khan", "patient123", "patient", phone="0301 5556677")
        omar = self._user("pat_omar", "Omar", "Ahmed", "patient123", "patient", phone="0302 9998877")
        for patient, dob, gender, blood, allergies in ((zara, (1994, 5, 17), "female", "O+", "Penicillin"),
                                                      (omar, (1988, 11, 2), "male", "A+", "none")):
            p = patient.patient_profile
            p.date_of_birth = __import__("datetime").date(*dob)
            p.gender, p.blood_group, p.allergies = gender, blood, allergies
            p.emergency_contact = "Family member, 0300 0000000"
            p.save()

        today = timezone.localdate()
        amina, bilal = profiles["dr_amina"], profiles["dr_bilal"]

        # 1. Zara: a finished, fully paid visit with prescriptions, an invoice and a lab report
        visit = Appointment.objects.create(patient=zara, doctor=amina, date=today - timedelta(days=7), start_time=time(9, 30),
                                           end_time=time(10, 0), reason="Persistent cough and tiredness", status="completed")
        consult = Consultation.objects.create(
            appointment=visit, symptoms="Dry cough for two weeks, mild fever in the evenings.", diagnosis="Acute bronchitis",
            notes="Chest clear on the right, mild wheeze on the left. Rest, fluids, avoid cold drinks. Review if fever continues.",
            blood_pressure="118/76", pulse=78, temperature=Decimal("37.8"), weight_kg=Decimal("62.5"),
            follow_up_date=today + timedelta(days=7))
        Prescription.objects.create(consultation=consult, medicine="Azithromycin", dosage="500 mg", frequency="Once a day after food", duration_days=3, instructions="Finish the full course.")
        Prescription.objects.create(consultation=consult, medicine="Cough syrup", dosage="10 ml", frequency="Three times a day", duration_days=5)
        invoice = Invoice.objects.create(patient=zara, appointment=visit, notes="Visit and blood test", created_by=User.objects.get(username="desk"))
        InvoiceItem.objects.create(invoice=invoice, description="Consultation with Dr. Amina Rahman", quantity=1, unit_price=Decimal("40.00"))
        InvoiceItem.objects.create(invoice=invoice, description="Complete blood count", quantity=1, unit_price=Decimal("15.00"))
        Payment.objects.create(invoice=invoice, amount=Decimal("55.00"), method="cash", received_by=User.objects.get(username="desk"))
        report = LabReport(patient=zara, uploaded_by=amina.user, title="Complete blood count", report_type="blood",
                           notes="Slightly raised white cell count, consistent with infection.")
        report.file.save("zara-cbc.txt", ContentFile(
            b"COMPLETE BLOOD COUNT\nPatient: Zara Khan\n\nHaemoglobin 13.1 g/dL (normal)\nWhite cells 11.8 x10^9/L (slightly high)\nPlatelets 260 x10^9/L (normal)\n"), save=False)
        report.save()

        # 2. Omar: a finished visit that still needs billing
        done = Appointment.objects.create(patient=omar, doctor=amina, date=today - timedelta(days=2), start_time=time(10, 0),
                                          end_time=time(10, 30), reason="Back pain after lifting", status="completed")
        c2 = Consultation.objects.create(appointment=done, symptoms="Lower back pain for three days.", diagnosis="Muscle strain",
                                         notes="No numbness. Gentle stretching and heat. Avoid heavy lifting for a week.",
                                         blood_pressure="125/82", pulse=72)
        Prescription.objects.create(consultation=c2, medicine="Ibuprofen", dosage="400 mg", frequency="Twice a day after meals", duration_days=5)

        # 3. Upcoming and today's appointments so every dashboard has something to show
        Appointment.objects.create(patient=omar, doctor=amina, date=today, start_time=time(16, 0), end_time=time(16, 30),
                                   reason="Follow up on back pain", created_by=omar)
        Appointment.objects.create(patient=zara, doctor=amina, date=today, start_time=time(16, 30), end_time=time(17, 0),
                                   reason="Cough review", created_by=User.objects.get(username="desk"))
        Appointment.objects.create(patient=zara, doctor=bilal, date=today + timedelta(days=3), start_time=time(14, 20),
                                   end_time=time(14, 40), reason="Vaccination advice", created_by=zara)

        self.stdout.write(self.style.SUCCESS(
            "Demo data created. Logins (username / password):\n"
            "  clinic_admin / admin123   (admin)\n"
            "  desk / desk123            (front desk)\n"
            "  dr_amina, dr_bilal, dr_chen / doctor123   (doctors)\n"
            "  pat_zara, pat_omar / patient123           (patients)"))

    def _user(self, username, first, last, password, role, superuser=False, phone=""):
        user = User(username=username, first_name=first, last_name=last, email=f"{username}@clinic.example", role=role, phone=phone)
        user.set_password(password)
        if superuser:
            user.is_staff = user.is_superuser = True
        user.save()
        return user
