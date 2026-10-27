from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from clinic.forms import PatientProfileForm
from clinic.models import PatientProfile

from .forms import AccountForm, RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome, {user.display_name}. Complete your health profile when you are ready.")
        return redirect("profile")
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    user = request.user
    account_form = AccountForm(request.POST or None, request.FILES or None, instance=user, prefix="a")
    patient_form = None
    if user.is_patient:
        profile_obj, _ = PatientProfile.objects.get_or_create(user=user)
        patient_form = PatientProfileForm(request.POST or None, instance=profile_obj, prefix="p")
    if request.method == "POST":
        ok = account_form.is_valid() and (patient_form is None or patient_form.is_valid())
        if ok:
            account_form.save()
            if patient_form:
                patient_form.save()
            messages.success(request, "Profile saved.")
            return redirect("profile")
    return render(request, "registration/profile.html", {"account_form": account_form, "patient_form": patient_form})
