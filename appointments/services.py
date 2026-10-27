from datetime import timedelta

from django.utils import timezone

from .models import ACTIVE_STATUSES, Appointment

MAX_DAYS_AHEAD = 60


def available_slots(doctor, day):
    """Open slots for a doctor on a date: [(start_time, end_time)]. Empty if the date is not bookable."""
    today = timezone.localdate()
    if day < today or day > today + timedelta(days=MAX_DAYS_AHEAD):
        return []
    taken = set(
        Appointment.objects.filter(doctor=doctor, date=day, status__in=ACTIVE_STATUSES).values_list("start_time", flat=True)
    )
    now = timezone.localtime().time() if day == today else None
    slots = {}
    for schedule in doctor.schedules.filter(weekday=day.weekday()):
        for start, end in schedule.slots(day):
            if start in taken or (now and start <= now):
                continue
            slots[start] = end
    return sorted(slots.items())
