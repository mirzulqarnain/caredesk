from django import forms

from .models import Consultation, LabReport, Prescription


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ("symptoms", "diagnosis", "notes", "blood_pressure", "pulse", "temperature", "weight_kg", "follow_up_date")
        widgets = {
            "symptoms": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "follow_up_date": forms.DateInput(attrs={"type": "date"}),
        }


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ("medicine", "dosage", "frequency", "duration_days", "instructions")


class LabReportForm(forms.ModelForm):
    class Meta:
        model = LabReport
        fields = ("title", "report_type", "notes", "file")
