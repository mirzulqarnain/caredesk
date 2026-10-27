from django import forms

from .models import PatientProfile, Schedule


class PatientProfileForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = ("date_of_birth", "gender", "blood_group", "allergies", "emergency_contact", "address")
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
        }


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ("weekday", "start_time", "end_time", "slot_minutes")
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, doctor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.doctor = doctor

    def clean(self):
        data = super().clean()
        start, end, day = data.get("start_time"), data.get("end_time"), data.get("weekday")
        if self.doctor and start and end and day is not None and end > start:
            clash = Schedule.objects.filter(doctor=self.doctor, weekday=day, start_time__lt=end, end_time__gt=start)
            if clash.exists():
                raise forms.ValidationError("This overlaps another working period on the same day.")
        return data


class PatientCreateForm(forms.Form):
    """Front desk registers a walk-in patient."""

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=30)
    password = forms.CharField(min_length=6, widget=forms.PasswordInput, help_text="Give this to the patient so they can log in.")
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    gender = forms.ChoiceField(choices=[("", "Not stated")] + PatientProfile.GENDERS, required=False)

    def clean_username(self):
        from accounts.models import User
        name = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=name).exists():
            raise forms.ValidationError("This username is taken.")
        return name
