import os

# Fix forms.py
form_path = r"c:\Users\asus\Desktop\Aakash SchSpa\ScholarSpacefinal\ScholarSpacefinal (1)\ScholarSpacefinal (1)\ScholarSpacefinal\ScholarSpace\ScholarSpace\django\ScholarSpace\manage_work\forms.py"
with open(form_path, "r", encoding="utf-8") as f:
    form_content = f.read()

if "gettext_lazy as _" not in form_content:
    form_content = form_content.replace("from django import forms", "from django import forms\nfrom django.utils.translation import gettext_lazy as _")
    form_content = form_content.replace('"Est. Hours Needed"', '_("Est. Hours Needed")')
    form_content = form_content.replace('"Deadline (Date & Time)"', '_("Deadline (Date & Time)")')
    form_content = form_content.replace('"Estimated hours must be greater than zero."', '_("Estimated hours must be greater than zero.")')
    form_content = form_content.replace('"Deadline must be in the future."', '_("Deadline must be in the future.")')
    
    with open(form_path, "w", encoding="utf-8") as f:
        f.write(form_content)

# Fix models.py
models_path = r"c:\Users\asus\Desktop\Aakash SchSpa\ScholarSpacefinal\ScholarSpacefinal (1)\ScholarSpacefinal (1)\ScholarSpacefinal\ScholarSpace\ScholarSpace\django\ScholarSpace\manage_work\models.py"
with open(models_path, "r", encoding="utf-8") as f:
    models_content = f.read()

if "gettext_lazy as _" not in models_content:
    models_content = models_content.replace("from django.db import models", "from django.db import models\nfrom django.utils.translation import gettext_lazy as _")
    models_content = models_content.replace('("assignment", "Assignment")', '("assignment", _("Assignment"))')
    models_content = models_content.replace('("exam",       "Exam")', '("exam",       _("Exam"))')
    models_content = models_content.replace('("hackathon",  "Hackathon")', '("hackathon",  _("Hackathon"))')
    models_content = models_content.replace('("project",    "Project")', '("project",    _("Project"))')
    models_content = models_content.replace('("critical", "Critical")', '("critical", _("Critical"))')
    models_content = models_content.replace('("high",     "High")', '("high",     _("High"))')
    models_content = models_content.replace('("medium",   "Medium")', '("medium",   _("Medium"))')
    models_content = models_content.replace('("low",      "Low")', '("low",      _("Low"))')
    models_content = models_content.replace('("mild",     "Mild")', '("mild",     _("Mild"))')
    models_content = models_content.replace('("moderate", "Moderate")', '("moderate", _("Moderate"))')
    
    with open(models_path, "w", encoding="utf-8") as f:
        f.write(models_content)

# Fix HTML files missing tags due to whitespace
html_fixes = {
    "base.html": [
        ("</span> Dashboard", "</span> {% trans 'Dashboard' %}"),
        ("</span> Add Deadline", "</span> {% trans 'Add Deadline' %}"),
        ("</span> My Tasks", "</span> {% trans 'My Tasks' %}"),
        ("</span> Calendar", "</span> {% trans 'Calendar' %}"),
        ("</span> Conflicts", "</span> {% trans 'Conflicts' %}"),
        ("</span> Smart Plan", "</span> {% trans 'Smart Plan' %}"),
        ("</span> Reminders", "</span> {% trans 'Reminders' %}"),
        ("</span> Analytics", "</span> {% trans 'Analytics' %}"),
        ("</span> SMS Settings", "</span> {% trans 'SMS Settings' %}"),
        ("</span> Activity Log", "</span> {% trans 'Activity Log' %}"),
        ("</span> Back to Dashboard", "</span> {% trans 'Back to Dashboard' %}"),
    ],
    "add_deadline.html": [
        ("\n          Add Deadline\n", "\n          {% trans 'Add Deadline' %}\n"),
        ("\n          Cancel\n", "\n          {% trans 'Cancel' %}\n"),
    ]
}

base_dir = r"c:\Users\asus\Desktop\Aakash SchSpa\ScholarSpacefinal\ScholarSpacefinal (1)\ScholarSpacefinal (1)\ScholarSpacefinal\ScholarSpace\ScholarSpace\django\ScholarSpace\manage_work\templates\manage_work"

for file_name, replacements in html_fixes.items():
    file_path = os.path.join(base_dir, file_name)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Updates completed successfully.")
