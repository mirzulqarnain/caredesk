from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from .models import InvoiceItem, Payment

User = get_user_model()


class InvoiceCreateForm(forms.Form):
    patient = forms.ModelChoiceField(queryset=User.objects.none())
    notes = forms.CharField(max_length=300, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = User.objects.filter(role="patient", is_active=True).order_by("first_name", "username")
        self.fields["patient"].label_from_instance = lambda u: f"{u.display_name} ({u.username})"


class ItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ("description", "quantity", "unit_price")

    def clean_unit_price(self):
        value = self.cleaned_data["unit_price"]
        if value <= 0:
            raise forms.ValidationError("Price must be more than zero.")
        return value

    def clean_quantity(self):
        value = self.cleaned_data["quantity"]
        if value < 1:
            raise forms.ValidationError("Quantity must be at least 1.")
        return value


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("amount", "method", "reference")
        labels = {"reference": "Receipt or card reference (optional)"}

    def __init__(self, *args, balance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.balance = balance
        self.fields["method"].choices = [c for c in Payment.METHODS if c[0] != "online"]
        if balance is not None:
            self.fields["amount"].initial = balance

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Enter an amount above zero.")
        if self.balance is not None and amount > self.balance:
            raise forms.ValidationError(f"The balance due is only {self.balance}.")
        return amount
