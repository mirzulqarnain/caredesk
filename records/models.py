from django.conf import settings
from django.db import models

from .validators import validate_report


class Consultation(models.Model):
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.CASCADE, related_name="consultation")
    symptoms = models.TextField(blank=True)
    diagnosis = models.CharField(max_length=240)
    notes = models.TextField(blank=True, help_text="Examination findings and advice.")
    blood_pressure = models.CharField(max_length=12, blank=True, help_text="For example 120/80")
    pulse = models.PositiveIntegerField(null=True, blank=True, help_text="Beats per minute")
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Degrees Celsius")
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-appointment__date", "-appointment__start_time"]

    def __str__(self):
        return f"Consultation for {self.appointment}"


class Prescription(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name="prescriptions")
    medicine = models.CharField(max_length=120)
    dosage = models.CharField(max_length=80, help_text="For example 500 mg")
    frequency = models.CharField(max_length=80, help_text="For example twice a day after meals")
    duration_days = models.PositiveIntegerField(default=5)
    instructions = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.medicine


class LabReport(models.Model):
    TYPES = [("blood", "Blood test"), ("urine", "Urine test"), ("imaging", "X-ray or scan"), ("other", "Other")]

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lab_reports")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField(max_length=140)
    report_type = models.CharField(max_length=10, choices=TYPES, default="blood")
    notes = models.CharField(max_length=300, blank=True)
    file = models.FileField(upload_to="lab_reports/", validators=[validate_report])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1]
