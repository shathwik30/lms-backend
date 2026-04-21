import json
import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Users"

    def ready(self):
        import apps.users.signals  # noqa: F401

        self._init_firebase()

    def _init_firebase(self):
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            return

        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "")
        cred_json = getattr(settings, "FIREBASE_CREDENTIALS_JSON", "")

        cred = None
        if cred_json:
            cred = credentials.Certificate(json.loads(cred_json))
        elif cred_path:
            cred = credentials.Certificate(cred_path)

        if cred is None:
            logger.warning("Firebase credentials not configured — Google auth will fail.")
            return

        firebase_admin.initialize_app(cred)
