from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class StaffCreateForm(forms.Form):
    """Admin creates doctor, front desk, admin or patient accounts."""

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=30, required=False)
    role = forms.ChoiceField(choices=User.Role.choices, initial="doctor")
    password = forms.CharField(min_length=6, widget=forms.PasswordInput)
    specialty = forms.CharField(max_length=80, required=False, help_text="Doctors only. For example Cardiology.")
    consultation_fee = forms.DecimalField(max_digits=8, decimal_places=2, required=False, min_value=0, help_text="Doctors only.")
    room = forms.CharField(max_length=40, required=False, help_text="Doctors only. For example Room 4.")

    def clean_username(self):
        name = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=name).exists():
            raise forms.ValidationError("This username is taken.")
        return name

    def clean(self):
        data = super().clean()
        if data.get("role") == "doctor" and not data.get("specialty"):
            self.add_error("specialty", "Enter the doctor's specialty.")
        return data
