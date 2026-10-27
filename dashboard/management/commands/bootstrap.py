"""Run on every deploy (EC2 setup script and Beanstalk container_commands).

Environment variables (all optional):
  ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL : create or update an admin account
  SEED_DEMO=True                              : load demo doctors, patients and records
"""
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the admin account and demo data from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if username and password:
            User = get_user_model()
            user, created = User.objects.get_or_create(username=username, defaults={
                "email": os.environ.get("ADMIN_EMAIL", f"{username}@clinic.example"),
                "is_staff": True, "is_superuser": True, "role": "admin",
            })
            user.is_staff = user.is_superuser = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Admin '{username}' {'created' if created else 'updated'}."))
        else:
            self.stdout.write("ADMIN_USERNAME / ADMIN_PASSWORD not set: skipping admin creation.")

        if os.environ.get("SEED_DEMO", "").lower() in ("1", "true", "yes", "on"):
            call_command("seed_demo")
        else:
            self.stdout.write("SEED_DEMO not enabled: skipping demo data.")
