from django.contrib import admin

from .models import DoctorProfile, PatientProfile, Schedule, Specialty


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0


@admin.register(DoctorProfile)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("name", "specialty", "consultation_fee", "room")
    inlines = [ScheduleInline]


admin.site.register(Specialty)
admin.site.register(PatientProfile)
admin.site.register(Schedule)
