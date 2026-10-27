from .models import Schedule

_DAYS = dict(Schedule.WEEKDAYS)


def doctor_rows(queryset):
    """Doctors with a short 'Mon, Wed, Fri' text for the cards."""
    rows = []
    for doctor in queryset.prefetch_related("schedules"):
        days = sorted({s.weekday for s in doctor.schedules.all()})
        rows.append({"doctor": doctor, "days": ", ".join(_DAYS[d][:3] for d in days) or "No schedule yet"})
    return rows
