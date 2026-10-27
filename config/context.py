from django.conf import settings


def site(request):
    return {"CLINIC_NAME": settings.CLINIC_NAME, "CURRENCY": settings.CURRENCY}
