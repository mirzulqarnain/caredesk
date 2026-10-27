"""Pre-flight check for a deployment. Prints what is wrong and how to fix it.

    python manage.py check_aws

Run automatically by deploy/ec2/setup.sh and by Elastic Beanstalk before migrations.
Exit code 0 = everything reachable, 1 = something to fix.
"""
import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Check that the database (RDS) and file storage (S3) are reachable."

    def handle(self, *args, **options):
        failures = 0
        failures += self._check_database()
        if settings.USE_S3:
            failures += self._check_s3()
        else:
            self.stdout.write("Storage : USE_S3 is False, files go to the local media folder (skipped S3 check).")
        if failures:
            self.stderr.write(self.style.ERROR("\nFix the problem(s) above, then run the installer again."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("\nAll checks passed."))

    # ------------------------------------------------------------------ database
    def _check_database(self):
        db = settings.DATABASES["default"]
        where = db.get("HOST") or "local SQLite file"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write(self.style.SUCCESS(f"Database: connected to {where}"))
            return 0
        except Exception as exc:
            text = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
            self.stderr.write(self.style.ERROR(f"Database: FAILED to connect to {where}\n  {text}"))
            lower = text.lower()
            if "timeout" in lower or "timed out" in lower:
                hint = ("The network is blocking port 5432. In the RDS security group add an inbound rule:\n"
                        "    type PostgreSQL, port 5432, source = the security group attached to THIS server.\n"
                        "  Also make sure RDS and this server are in the same VPC.")
            elif "password authentication" in lower:
                hint = "Wrong DB_USER or DB_PASSWORD in .env."
            elif "does not exist" in lower and "database" in lower:
                hint = "The database name does not exist. Check DB_NAME, or run CREATE DATABASE from psql."
            elif "could not translate host" in lower or "name or service not known" in lower:
                hint = "DB_HOST is wrong. Copy the endpoint from the RDS console."
            elif "refused" in lower:
                hint = "Nothing is listening there. Check DB_HOST and that the RDS instance is Available (not stopped)."
            else:
                hint = "Check DB_HOST, DB_NAME, DB_USER and DB_PASSWORD in .env."
            self.stderr.write(f"  Hint: {hint}")
            return 1

    # ------------------------------------------------------------------ S3
    def _check_s3(self):
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        region = settings.AWS_S3_REGION_NAME
        if not bucket:
            self.stderr.write(self.style.ERROR("Storage : USE_S3 is True but AWS_STORAGE_BUCKET_NAME is empty in .env."))
            return 1
        name = f"healthcheck/preflight-{int(time.time())}.txt"
        try:
            saved = default_storage.save(name, ContentFile(b"preflight"))
            ok = default_storage.open(saved, "rb").read() == b"preflight"
            default_storage.delete(saved)
            if not ok:
                raise RuntimeError("Read back did not match what was written.")
            self.stdout.write(self.style.SUCCESS(f"Storage : S3 bucket '{bucket}' ({region}) can write, read and delete"))
            return 0
        except Exception as exc:
            kind = type(exc).__name__
            text = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
            self.stderr.write(self.style.ERROR(f"Storage : FAILED on S3 bucket '{bucket}'\n  {kind}: {text}"))
            if kind == "NoCredentialsError":
                hint = ("This server has no AWS credentials. Attach the IAM role:\n"
                        "    EC2 console > select instance > Actions > Security > Modify IAM role > choose your role.\n"
                        "  The role needs the S3 policy from deploy/aws/s3-policy.json.")
            elif "AccessDenied" in text or "403" in text:
                hint = ("The role exists but is not allowed. Attach the policy in deploy/aws/s3-policy.json to it\n"
                        "  and check the bucket name inside the policy matches AWS_STORAGE_BUCKET_NAME.")
            elif "NoSuchBucket" in text or "404" in text:
                hint = "The bucket name is wrong or it does not exist. Check AWS_STORAGE_BUCKET_NAME."
            elif "301" in text or "PermanentRedirect" in text or "region" in text.lower():
                hint = f"The bucket is in a different region. Set AWS_S3_REGION_NAME to the bucket's real region (now {region})."
            elif "Could not connect" in text or "EndpointConnectionError" in kind:
                hint = "No route to S3. Check the server has internet access (public IP or NAT) and AWS_S3_REGION_NAME."
            else:
                hint = "Check AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME and the IAM role."
            self.stderr.write(f"  Hint: {hint}")
            return 1
