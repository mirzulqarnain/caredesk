from django.contrib import admin

from .models import Consultation, LabReport, Prescription


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 0


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("appointment", "diagnosis", "created_at")
    inlines = [PrescriptionInline]


admin.site.register(LabReport)
