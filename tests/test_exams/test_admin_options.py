from django.test import TestCase
from rest_framework import status

from apps.exams.models import Option
from core.test_utils import TestFactory


class AdminOptionDetailViewTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()
        self.student_client = self.factory.get_auth_client(self.student_user)

        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level)
        self.question, self.correct_option = self.factory.create_question(self.exam)
        self.option = Option.objects.filter(question=self.question, is_correct=False).first()

    def test_retrieve_option(self):
        response = self.admin_client.get(f"/api/v1/exams/admin/options/{self.option.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.option.pk)

    def test_update_option(self):
        response = self.admin_client.put(
            f"/api/v1/exams/admin/options/{self.option.pk}/",
            data={
                "question": self.question.pk,
                "text": "Updated option text",
                "is_correct": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.option.refresh_from_db()
        self.assertEqual(self.option.text, "Updated option text")

    def test_partial_update_option(self):
        response = self.admin_client.patch(
            f"/api/v1/exams/admin/options/{self.option.pk}/",
            data={"text": "Partially updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.option.refresh_from_db()
        self.assertEqual(self.option.text, "Partially updated")

    def test_delete_option(self):
        option_pk = self.option.pk
        response = self.admin_client.delete(f"/api/v1/exams/admin/options/{option_pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Option.objects.filter(pk=option_pk).exists())

    def test_not_found(self):
        response = self.admin_client.get("/api/v1/exams/admin/options/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_access(self):
        response = self.student_client.get(f"/api/v1/exams/admin/options/{self.option.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
