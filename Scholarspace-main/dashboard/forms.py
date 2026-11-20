from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.forms import widgets

from .models import *
from .models import Notes


class NotesForm(forms.ModelForm):
    class Meta:
        model = Notes
        fields = ["title", "description", "pdf_file"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Enter Note Title"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "placeholder": "Enter Note Description"}
            ),
        }


class DateInput(forms.DateInput):
    input_type = "date"


class HomeworkForm(forms.ModelForm):
    class Meta:
        model = Homework
        widgets = {"due": DateInput()}
        fields = ["subject", "title", "description", "due", "is_finished"]


class DashboardForm(forms.Form):
    text = forms.CharField(max_length=100, label="Enter Your Search:")


class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ["title", "is_finished"]


class ConversionForm(forms.Form):
    CHOICES = [
        ("length", "Length"),
        ("mass", "Mass"),
        ("time", "Time"),
        ("temperature", "Temperature"),
        ("electric_current", "Electric Current"),
        ("amount_substance", "Amount of Substance"),
        ("luminous_intensity", "Luminous Intensity"),
    ]
    measurement = forms.ChoiceField(choices=CHOICES, widget=forms.RadioSelect)


class ConversionLengthForm(forms.Form):
    CHOICES = [("yard", "Yard"), ("foot", "Foot")]
    input = forms.CharField(
        required=False,
        label=False,
        widget=forms.TextInput(
            attrs={"type": "number", "placeholder": "Enter the number"}
        ),
    )
    measure1 = forms.CharField(label="", widget=forms.Select(choices=CHOICES))
    measure2 = forms.CharField(label="", widget=forms.Select(choices=CHOICES))


class ConversionMassForm(forms.Form):
    CHOICES = [("pound", "Pound"), ("kilogram", "Kilogram")]
    input = forms.CharField(
        required=False,
        label=False,
        widget=forms.TextInput(
            attrs={"type": "number", "placeholder": "Enter the number"}
        ),
    )
    measure1 = forms.CharField(label="", widget=forms.Select(choices=CHOICES))
    measure2 = forms.CharField(label="", widget=forms.Select(choices=CHOICES))


class ConversionTimeForm(forms.Form):
    TIME_CHOICES = [("second", "Second"), ("minute", "Minute"), ("hour", "Hour")]
    input = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"type": "number", "placeholder": "Enter the number"}
        ),
    )
    measure1 = forms.CharField(label="", widget=forms.Select(choices=TIME_CHOICES))
    measure2 = forms.CharField(label="", widget=forms.Select(choices=TIME_CHOICES))


class ConversionTemperatureForm(forms.Form):
    TEMP_CHOICES = [
        ("celsius", "Celsius"),
        ("fahrenheit", "Fahrenheit"),
        ("kelvin", "Kelvin"),
    ]
    input = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"type": "number", "placeholder": "Enter the temperature"}
        ),
    )
    measure1 = forms.CharField(label="", widget=forms.Select(choices=TEMP_CHOICES))
    measure2 = forms.CharField(label="", widget=forms.Select(choices=TEMP_CHOICES))


class ConversionElectricCurrentForm(forms.Form):
    CURRENT_CHOICES = [("ampere", "Ampere"), ("milliampere", "Milliampere")]
    input = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"type": "number", "placeholder": "Enter the current"}
        ),
    )
    measure1 = forms.CharField(label="", widget=forms.Select(choices=CURRENT_CHOICES))
    measure2 = forms.CharField(label="", widget=forms.Select(choices=CURRENT_CHOICES))


class ConversionAmountSubstanceForm(forms.Form):
    SUBSTANCE_CHOICES = [("mole", "Mole"), ("millimole", "Millimole")]
    input = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"type": "number", "placeholder": "Enter the amount"}
        ),
    )
    measure1 = forms.CharField(label="", widget=forms.Select(choices=SUBSTANCE_CHOICES))
    measure2 = forms.CharField(label="", widget=forms.Select(choices=SUBSTANCE_CHOICES))


class ConversionLuminousIntensityForm(forms.Form):
    INTENSITY_CHOICES = [("candela", "Candela"), ("millicandela", "Millicandela")]
    input = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"type": "number", "placeholder": "Enter the intensity"}
        ),
    )
    measure1 = forms.CharField(label="", widget=forms.Select(choices=INTENSITY_CHOICES))
    measure2 = forms.CharField(label="", widget=forms.Select(choices=INTENSITY_CHOICES))


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        help_text="Optional but needed for deadline reminders.",
        widget=forms.EmailInput(
            attrs={
                "class": "w-full bg-transparent border-none focus:ring-0 py-4 px-3 text-on-surface placeholder:text-outline-variant text-sm",
                "placeholder": "you@university.edu",
                "autocomplete": "email",
            }
        ),
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        help_text="Optional. E.g. +919876543210",
        widget=forms.TextInput(
            attrs={
                "class": "w-full bg-transparent border-none focus:ring-0 py-4 px-3 text-on-surface placeholder:text-outline-variant text-sm",
                "placeholder": "+91 98765 43210",
                "autocomplete": "tel",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full bg-transparent border-none focus:ring-0 py-4 px-3 text-on-surface placeholder:text-outline-variant text-sm",
                    "placeholder": "scholarly_mind",
                    "autocomplete": "username",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = ""
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""
        self.fields["password1"].widget.attrs.update(
            {
                "class": "w-full bg-transparent border-none focus:ring-0 py-4 px-3 text-on-surface placeholder:text-outline-variant text-sm",
                "placeholder": "••••••••",
                "autocomplete": "new-password",
            }
        )
        self.fields["password2"].widget.attrs.update(
            {
                "class": "w-full bg-transparent border-none focus:ring-0 py-4 px-3 text-on-surface placeholder:text-outline-variant text-sm",
                "placeholder": "••••••••",
                "autocomplete": "new-password",
            }
        )


LOGIN_INPUT_CLASS = (
    "w-full pl-12 pr-4 py-4 bg-surface-container-high rounded-lg border-none "
    "focus:ring-2 focus:ring-primary focus:bg-surface-container-lowest transition-all "
    "placeholder:text-outline-variant text-on-surface"
)


class ScholarSpaceAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = ""
        self.fields["password"].label = ""
        self.fields["username"].widget.attrs.update(
            {
                "class": LOGIN_INPUT_CLASS,
                "placeholder": "name@university.edu",
                "autocomplete": "username",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": LOGIN_INPUT_CLASS,
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        )


    def clean_phone_number(self):
        """Normalize to E.164 and validate format."""
        import re as _re
        phone = (self.cleaned_data.get('phone_number') or '').strip()
        if not phone:
            return phone
        # Strip spaces, dashes, dots
        phone = _re.sub(r'[\s\-\.\(\)]', '', phone)
        # Auto-prepend + if missing
        if not phone.startswith('+'):
            phone = '+' + phone
        # Must be + followed by 7-15 digits
        if not _re.fullmatch(r'\+\d{7,15}', phone):
            from django import forms
            raise forms.ValidationError(
                'Enter a valid phone number with country code (e.g. +919876543210).'
            )
        return phone

    def clean_email(self):
        """Lower-case and check email is not already registered."""
        from django.contrib.auth import get_user_model
        _User = get_user_model()
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email and _User.objects.filter(email__iexact=email).exists():
            from django import forms
            raise forms.ValidationError(
                'An account with this email already exists. Try signing in instead.'
            )
        return email


# Backward-compat alias
UserRegistrationForm = RegisterForm
