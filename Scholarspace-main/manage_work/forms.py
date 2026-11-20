from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Deadline


class DeadlineForm(forms.ModelForm):
    class Meta:
        model  = Deadline
        fields = ["title", "type", "priority", "deadline_at", "est_hours", "notes"]
        widgets = {
            "deadline_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Any context, resources, or reminders...",
            }),
            "est_hours": forms.NumberInput(attrs={
                "step": "0.5",
                "min":  "0.5",
                "placeholder": "e.g. 8",
            }),
        }
        labels = {
            "est_hours":   _("Est. Hours Needed"),
            "deadline_at": _("Deadline (Date & Time)"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["notes"].required    = False
        self.fields["est_hours"].initial = 1.0

    def clean_est_hours(self):
        val = self.cleaned_data.get("est_hours", 1.0)
        if val is None or val <= 0:
            raise forms.ValidationError(_("Estimated hours must be greater than zero."))
        return val

    def clean_deadline_at(self):
        from django.utils import timezone
        dt = self.cleaned_data.get("deadline_at")
        if dt and dt < timezone.now():
            raise forms.ValidationError(_("Deadline must be in the future."))
        return dt
