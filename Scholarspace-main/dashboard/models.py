from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator

# Create your models here.
from django.db import models


class Notes(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    pdf_file = models.FileField(
        upload_to="notes_pdfs/",
        validators=[FileExtensionValidator(["pdf"])],
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "notes"
        verbose_name_plural = "notes"


class Homework(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=50)
    title = models.CharField(max_length=50)
    description = models.TextField()
    due = models.DateTimeField()
    is_finished = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class Todo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    is_finished = models.BooleanField(default=False)

    def __str__(self):
        return self.title


from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=20, blank=True, default="")
    timezone = models.CharField(max_length=60, default="Asia/Kolkata")

    def __str__(self):
        return f"Profile({self.user.username})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Auto-create a UserProfile whenever a new User is saved."""
    UserProfile.objects.get_or_create(user=instance)


# ── Notifications ─────────────────────────────────────────────────────────────

class Notification(models.Model):
    TYPE_CHOICES = [
        ("welcome",  "Welcome"),
        ("homework", "Homework"),
        ("todo",     "Goal"),
        ("deadline", "Deadline"),
        ("notes",    "Note"),
        ("system",   "System"),
    ]
    user       = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_notifications"
    )
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="system")
    icon       = models.CharField(max_length=50, default="notifications")
    link       = models.CharField(max_length=300, blank=True, default="")
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notif_type}: {self.title} ({self.user.username})"


def push_notification(user, title, message, notif_type="system",
                      icon="notifications", link=""):
    """Create a Notification for *user*. Silently swallows any DB error."""
    try:
        Notification.objects.create(
            user=user, title=title, message=message,
            notif_type=notif_type, icon=icon, link=link,
        )
    except Exception:
        pass
