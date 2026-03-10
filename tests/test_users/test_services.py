from django.test import TestCase

from apps.users.models import UserPreference
from apps.users.services import ProfileService
from core.test_utils import TestFactory


class ProfileServiceUpdatePreferencesTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student()

    def test_creates_preferences_if_not_exists(self):
        self.assertFalse(UserPreference.objects.filter(user=self.user).exists())
        prefs = ProfileService.update_preferences(self.user, {"push_notifications": False})
        self.assertFalse(prefs.push_notifications)
        self.assertTrue(UserPreference.objects.filter(user=self.user).exists())

    def test_updates_existing_preferences(self):
        UserPreference.objects.create(user=self.user)
        prefs = ProfileService.update_preferences(self.user, {"email_notifications": False})
        self.assertFalse(prefs.email_notifications)
        self.assertTrue(prefs.push_notifications)

    def test_updates_multiple_fields(self):
        prefs = ProfileService.update_preferences(
            self.user,
            {"push_notifications": False, "promotional_notifications": False},
        )
        self.assertFalse(prefs.push_notifications)
        self.assertFalse(prefs.promotional_notifications)
        self.assertTrue(prefs.email_notifications)
