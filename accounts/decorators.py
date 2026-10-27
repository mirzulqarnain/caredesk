from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Login required, and the user's role must be one of `roles`."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


patient_required = role_required("patient")
doctor_required = role_required("doctor")
ops_required = role_required("staff", "admin")          # front desk or admin
clinical_required = role_required("doctor", "admin")
admin_required = role_required("admin")
