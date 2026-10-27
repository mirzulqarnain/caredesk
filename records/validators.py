import os

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED = {"pdf", "png", "jpg", "jpeg", "txt", "doc", "docx", "csv"}


def validate_report(file):
    ext = os.path.splitext(file.name)[1].lower().lstrip(".")
    if ext not in ALLOWED:
        raise ValidationError(f"Upload one of: {', '.join(sorted(ALLOWED))}.")
    if file.size > settings.MAX_FILE_MB * 1024 * 1024:
        raise ValidationError(f"File is larger than {settings.MAX_FILE_MB} MB.")
