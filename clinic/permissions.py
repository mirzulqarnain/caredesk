from django.contrib.auth import get_user_model

User = get_user_model()


def patients_of_doctor(doctor_user):
    """Patients who have (or had) an appointment with this doctor."""
    return User.objects.filter(role="patient", appointments__doctor__user=doctor_user).distinct()


def can_view_clinical(user, patient):
    """Medical notes, prescriptions and lab reports: the patient, their doctors, and admins.
    Front desk staff never see clinical content."""
    if not user.is_authenticated:
        return False
    if user.pk == patient.pk or user.is_clinic_admin:
        return True
    return user.is_doctor and patients_of_doctor(user).filter(pk=patient.pk).exists()


def can_view_patient(user, patient):
    """The patient list and demographic page: front desk, admins, and the patient's doctors."""
    if not user.is_authenticated:
        return False
    if user.runs_operations:
        return True
    return user.is_doctor and patients_of_doctor(user).filter(pk=patient.pk).exists()
