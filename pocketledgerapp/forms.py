from calendar import month_name

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Budget, Category, CurrencyPreference, Transaction


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False, max_length=254)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class CurrencyPreferenceForm(forms.Form):
    currency = forms.ChoiceField(choices=CurrencyPreference.Currency.choices)


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ("kind", "title", "amount", "category", "date", "note")
        widgets = {
            "kind": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 100}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.01", "step": "0.01"}
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "note": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 240}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.filter(user=user)
        self.fields["date"].input_formats = ["%Y-%m-%d"]

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        kind = cleaned_data.get("kind")
        if category and kind and category.kind != kind:
            self.add_error("category", "Choose a category that matches the transaction type.")
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "kind")
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "maxlength": 40, "placeholder": "e.g. Travel"}
            ),
            "kind": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name", "").strip()
        kind = cleaned_data.get("kind")
        if self.user and Category.objects.filter(
            user=self.user, kind=kind, name__iexact=name
        ).exists():
            self.add_error("name", "You already have a category with this name and type.")
        cleaned_data["name"] = name
        return cleaned_data


class BudgetForm(forms.ModelForm):
    year = forms.IntegerField(
        min_value=2000,
        max_value=9999,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 2000, "max": 9999}
        ),
    )
    month = forms.TypedChoiceField(
        choices=[(month, month_name[month]) for month in range(1, 13)],
        coerce=int,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Budget
        fields = ("category", "amount", "year", "month")
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.01", "step": "0.01"}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.filter(
            user=user, kind=Category.Kind.EXPENSE
        )
        self.fields["category"].required = False
        self.fields["category"].empty_label = "Overall monthly budget"
        now = timezone.localdate()
        self.fields["year"].initial = now.year
        self.fields["month"].initial = now.month

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        if category and (category.user_id != self.user.pk or category.kind != Category.Kind.EXPENSE):
            self.add_error("category", "Choose one of your expense categories.")
        return cleaned_data
