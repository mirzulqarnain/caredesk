from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Specialty(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "specialties"

    def __str__(self):
        return self.name


class DoctorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile")
    specialty = models.ForeignKey(Specialty, null=True, blank=True, on_delete=models.SET_NULL, related_name="doctors")
    bio = models.TextField(blank=True)
    consultation_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("50.00"))
    room = models.CharField(max_length=40, blank=True)
    years_experience = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["user__first_name", "user__username"]

    def __str__(self):
        return self.name

    @property
    def name(self):
        return f"Dr. {self.user.display_name}"


class PatientProfile(models.Model):
    GENDERS = [("female", "Female"), ("male", "Male"), ("other", "Other")]
    BLOOD = [(b, b) for b in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_profile")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDERS, blank=True)
    blood_group = models.CharField(max_length=4, choices=BLOOD, blank=True)
    allergies = models.TextField(blank=True, help_text="Medicines or foods you react to. Write 'none' if there are none.")
    emergency_contact = models.CharField(max_length=120, blank=True, help_text="Name and phone number.")
    address = models.CharField(max_length=240, blank=True)

    def __str__(self):
        return f"Profile of {self.user}"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))


class Schedule(models.Model):
    WEEKDAYS = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveIntegerField(default=30, help_text="Length of one appointment in minutes.")

    class Meta:
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.doctor} {self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")
        if self.slot_minutes and not 10 <= self.slot_minutes <= 120:
            raise ValidationError("Appointment length must be between 10 and 120 minutes.")

    def slots(self, day):
        """Return [(start_time, end_time)] for one date."""
        cursor = datetime.combine(day, self.start_time)
        end = datetime.combine(day, self.end_time)
        step = timedelta(minutes=self.slot_minutes)
        out = []
        while cursor + step <= end:
            out.append((cursor.time(), (cursor + step).time()))
            cursor += step
        return out
