import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentProfile, User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_student_profile(sender, instance, created, **kwargs):
    """Auto-create StudentProfile when a student user is created."""
    if created and instance.is_student:
        try:
            StudentProfile.objects.get_or_create(user=instance)
        except Exception:
            logger.exception("Failed to create StudentProfile for user %s", instance.email)
