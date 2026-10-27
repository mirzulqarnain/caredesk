from datetime import datetime

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

ACTIVE_STATUSES = ("scheduled", "completed")


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No show"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey("clinic.DoctorProfile", on_delete=models.CASCADE, related_name="appointments")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "start_time"]
        constraints = [
            # A doctor cannot have two live appointments in the same slot. Cancelled slots become free again.
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                condition=Q(status__in=ACTIVE_STATUSES),
                name="one_live_appointment_per_slot",
            )
        ]

    def __str__(self):
        return f"{self.patient} with {self.doctor} on {self.date} {self.start_time:%H:%M}"

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    @property
    def is_future(self):
        return self.starts_at > timezone.now()

    @property
    def can_cancel(self):
        return self.status == self.Status.SCHEDULED and self.is_future

    @property
    def badge(self):
        return {"scheduled": "", "completed": "ok", "cancelled": "bad", "no_show": "warn"}[self.status]
