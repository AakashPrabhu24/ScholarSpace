import threading
import time
import logging

logger = logging.getLogger(__name__)

_thread_started = False
_thread_lock    = threading.Lock()


# ── Twilio helper ─────────────────────────────────────────────────────────────

def _send_sms(to_phone, body):
    """
    Send a single SMS via Twilio.
    Returns True on success, False on any failure (including missing config).
    Never raises.
    """
    if not to_phone:
        return False

    from django.conf import settings
    sid    = getattr(settings, "TWILIO_ACCOUNT_SID",  "").strip()
    token  = getattr(settings, "TWILIO_AUTH_TOKEN",   "").strip()
    fromno = getattr(settings, "TWILIO_PHONE_NUMBER", "").strip()

    if not all([sid, token, fromno]):
        logger.warning(
            "[manage_work] Twilio credentials not configured — "
            "set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER"
        )
        return False

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        msg = client.messages.create(body=body, from_=fromno, to=to_phone)
        logger.info(
            f"[manage_work] SMS sent to {to_phone}  sid={msg.sid}"
        )
        return True
    except Exception as exc:
        logger.error(f"[manage_work] Twilio SMS failed to {to_phone}: {exc}")
        return False


# ── Daemon reminder loop ──────────────────────────────────────────────────────

def send_due_reminders():
    """
    Daemon thread — wakes every 60 seconds and dispatches any due reminders.
    Email and SMS are sent independently so one failing does not block the other.
    """
    time.sleep(5)   # give Django full startup time
    while True:
        try:
            _process_due_reminders()
        except Exception as exc:
            logger.error(f"[manage_work] reminder loop unhandled error: {exc}")
        time.sleep(60)


def _process_due_reminders():
    from django.utils import timezone
    from django.core.mail import send_mail
    from django.conf import settings
    from .models import DeadlineReminder
    from .utils import log_event

    now = timezone.now()
    due = DeadlineReminder.objects.filter(
        is_sent=False,
        remind_at__lte=now,
    ).select_related("user", "deadline")

    for reminder in due:
        user     = reminder.user
        deadline = reminder.deadline

        # If the deadline was already completed, just mark and skip
        if deadline.is_completed:
            reminder.is_sent = True
            reminder.sent_at = now
            reminder.save(update_fields=["is_sent", "sent_at"])
            continue

        hours_before = round(
            (deadline.deadline_at - now).total_seconds() / 3600, 1
        )
        hours_display = max(round(hours_before, 1), 0)

        # ── Build message bodies ──────────────────────────────────────────
        email_subject = (
            f'[ScholarSpace] Reminder: "{deadline.title}" '
            f'due in ~{hours_display}h'
        )
        email_body = (
            f'Hi {user.username},\n\n'
            f'Your task "{deadline.title}" is coming up soon.\n\n'
            f'  Type:      {deadline.get_type_display()}\n'
            f'  Priority:  {deadline.get_priority_display()}\n'
            f'  Due:       {deadline.deadline_at.strftime("%d %b %Y %H:%M")} UTC\n'
            f'  Est. work: {deadline.est_hours} hours\n\n'
            f'Open ScholarSpace → Manage Work → Smart Plan to review your tasks.\n\n'
            f'— ScholarSpace'
        )
        sms_body = (
            f'[ScholarSpace] Hi {user.username}! '
            f'"{deadline.title}" ({deadline.get_priority_display()} priority) '
            f'is due in ~{hours_display}h. '
            f'Type: {deadline.get_type_display()}. '
            f'Est. {deadline.est_hours}h of work. '
            f'Check ScholarSpace for your Smart Plan.'
        )

        # ── Send via channel ──────────────────────────────────────────────
        sent_ok = False

        if reminder.channel == "email":
            if user.email:
                try:
                    send_mail(
                        subject=email_subject,
                        message=email_body,
                        from_email=getattr(
                            settings, "DEFAULT_FROM_EMAIL",
                            settings.EMAIL_HOST_USER,
                        ),
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    logger.info(
                        f'[manage_work] Email sent → {user.email} '
                        f'for "{deadline.title}" ({hours_display}h before)'
                    )
                    sent_ok = True
                except Exception as exc:
                    logger.error(
                        f'[manage_work] Email failed for {user.email}: {exc}'
                    )
            else:
                logger.warning(
                    f'[manage_work] No email for {user.username} — email reminder skipped'
                )

        elif reminder.channel == "sms":
            # Resolve phone number from UserProfile
            phone = ""
            try:
                from dashboard.models import UserProfile
                profile = UserProfile.objects.get(user=user)
                phone = (profile.phone_number or "").strip()
            except Exception:
                pass

            if phone:
                sent_ok = _send_sms(phone, sms_body)
            else:
                logger.warning(
                    f'[manage_work] No phone for {user.username} — SMS reminder skipped'
                )

        # ── Mark reminder as sent ─────────────────────────────────────────
        reminder.is_sent = True
        reminder.sent_at = now
        reminder.save(update_fields=["is_sent", "sent_at"])

        if sent_ok:
            log_event(user, "reminder_sent", deadline=deadline, metadata={
                "title":        deadline.title,
                "hours_before": hours_display,
                "channel":      reminder.channel,
                "user_email":   user.email or "",
            })


def start_reminder_thread():
    global _thread_started
    with _thread_lock:
        if not _thread_started:
            t = threading.Thread(
                target=send_due_reminders, daemon=True, name="mw-reminders"
            )
            t.start()
            _thread_started = True
            logger.info("[manage_work] Reminder background thread started.")
