from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Exam
from .session_sync import ExamSessionSyncService


@receiver(post_save, sender=Exam)
def sync_weekly_exam_session(sender, instance: Exam, **kwargs) -> None:
    ExamSessionSyncService.sync_exam_session(instance)


@receiver(post_delete, sender=Exam)
def delete_linked_exam_sessions(sender, instance: Exam, **kwargs) -> None:
    ExamSessionSyncService.delete_linked_sessions(instance)
