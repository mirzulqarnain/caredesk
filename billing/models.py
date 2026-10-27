from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Invoice(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices")
    appointment = models.OneToOneField("appointments.Appointment", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice")
    number = models.CharField(max_length=20, unique=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    is_void = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f"INV-{self.pk:05d}"
            super().save(update_fields=["number"])

    def __str__(self):
        return self.number

    @property
    def total(self):
        return sum((i.amount for i in self.items.all()), Decimal("0"))

    @property
    def paid(self):
        return sum((p.amount for p in self.payments.all()), Decimal("0"))

    @property
    def balance(self):
        return self.total - self.paid

    @property
    def status(self):
        if self.is_void:
            return "void"
        if self.total == 0:
            return "draft"
        if self.balance <= 0:
            return "paid"
        return "partial" if self.paid > 0 else "unpaid"

    @property
    def badge(self):
        return {"paid": "ok", "partial": "warn", "unpaid": "bad", "void": "plain", "draft": "plain"}[self.status]

    @property
    def can_edit_items(self):
        return not self.is_void and not self.payments.exists()


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]

    @property
    def amount(self):
        return self.quantity * self.unit_price


class Payment(models.Model):
    METHODS = [("cash", "Cash"), ("card", "Card at the desk"), ("online", "Online (simulated)")]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHODS, default="cash")
    reference = models.CharField(max_length=60, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    paid_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["paid_at"]
