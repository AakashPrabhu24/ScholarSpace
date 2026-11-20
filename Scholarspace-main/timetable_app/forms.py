from django import forms
from django.core.exceptions import ValidationError


class TimetableForm(forms.Form):
    STUDY_CHOICES = [
        ('day', 'Day'),
        ('night', 'Night'),
        ('both', 'Both'),
    ]

    STREAM_CHOICES = [
        ('science', 'Science'),
        ('commerce', 'Commerce'),
        ('arts', 'Arts'),
        ('engineering', 'Engineering'),
        ('medical', 'Medical'),
        ('other', 'Other'),
    ]

    EDUCATION_LEVEL_CHOICES = [
        ('10th', '10th Standard'),
        ('12th', '12th Standard'),
        ('graduation', 'Graduation'),
        ('post_graduation', 'Post Graduation'),
    ]

    JOB_CHOICES = [
        ('none', 'No Job'),
        ('part_time', 'Part Time'),
        ('full_time', 'Full Time'),
    ]

    study_preference = forms.ChoiceField(choices=STUDY_CHOICES, label='Which time is preferable for you to study?')
    stream = forms.ChoiceField(choices=STREAM_CHOICES, label='In which stream are you?')
    education_level = forms.ChoiceField(choices=EDUCATION_LEVEL_CHOICES, label='What is your educational level?')

    job_status = forms.ChoiceField(choices=JOB_CHOICES, label='Are you working?')
    job_hours = forms.IntegerField(min_value=0, max_value=12, required=False, label='How many hours do you work per day?')

    attending_classes = forms.BooleanField(required=False, label='Do you go to any classes?')
    class_hours = forms.IntegerField(min_value=0, max_value=12, required=False, label='How many hours do you spend in classes per day?')

    preparing_for_exam = forms.BooleanField(required=False, label='Are you preparing for any competitive exams?')
    exam_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label='When is the exam?')

    daily_activities_hours = forms.IntegerField(min_value=0, max_value=24, label='How many hours are you spending for your daily unavoidable activities?')

    language1_name = forms.CharField(max_length=50, required=False, label='Language 1 Name')
    language1_level = forms.IntegerField(min_value=0, max_value=100, required=False, label='Language 1 Preparation Level (%)')

    language2_name = forms.CharField(max_length=50, required=False, label='Language 2 Name')
    language2_level = forms.IntegerField(min_value=0, max_value=100, required=False, label='Language 2 Preparation Level (%)')

    subject1_name = forms.CharField(max_length=50, required=False, label='Subject 1 Name')
    subject1_level = forms.IntegerField(min_value=0, max_value=100, required=False, label='Subject 1 Preparation Level (%)')

    subject2_name = forms.CharField(max_length=50, required=False, label='Subject 2 Name')
    subject2_level = forms.IntegerField(min_value=0, max_value=100, required=False, label='Subject 2 Preparation Level (%)')

    subject3_name = forms.CharField(max_length=50, required=False, label='Subject 3 Name')
    subject3_level = forms.IntegerField(min_value=0, max_value=100, required=False, label='Subject 3 Preparation Level (%)')

    subject4_name = forms.CharField(max_length=50, required=False, label='Subject 4 Name')
    subject4_level = forms.IntegerField(min_value=0, max_value=100, required=False, label='Subject 4 Preparation Level (%)')

    force_majeure_days = forms.IntegerField(min_value=0, max_value=30, label='Number of days to be kept for Force Majeure?')
    revision_days = forms.IntegerField(min_value=0, max_value=60, label='How many days can be spent for your revision?')

    def clean(self):
        cleaned = super().clean()
        if not cleaned:
            return cleaned

        if cleaned.get('job_status') == 'none':
            cleaned['job_hours'] = 0
        elif cleaned.get('job_hours') is None:
            raise ValidationError({'job_hours': 'Enter hours per day when you have a job.'})

        if not cleaned.get('attending_classes'):
            cleaned['class_hours'] = cleaned.get('class_hours') or 0
        elif cleaned.get('class_hours') is None:
            raise ValidationError({'class_hours': 'Enter class hours per day when attending classes.'})

        if cleaned.get('preparing_for_exam') and not cleaned.get('exam_date'):
            raise ValidationError({'exam_date': 'Choose an exam date when preparing for an exam.'})

        pairs = [
            (cleaned.get('language1_name'), cleaned.get('language1_level')),
            (cleaned.get('language2_name'), cleaned.get('language2_level')),
            (cleaned.get('subject1_name'), cleaned.get('subject1_level')),
            (cleaned.get('subject2_name'), cleaned.get('subject2_level')),
            (cleaned.get('subject3_name'), cleaned.get('subject3_level')),
            (cleaned.get('subject4_name'), cleaned.get('subject4_level')),
        ]
        has_subject = False
        for name, level in pairs:
            name = (name or '').strip()
            if name and level is not None:
                has_subject = True
                break
        if not has_subject:
            raise ValidationError(
                'Add at least one subject or language with a name and preparation level (0–100).'
            )

        return cleaned
