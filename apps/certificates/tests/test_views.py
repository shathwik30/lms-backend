import uuid
from unittest import mock

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.certificates.models import Certificate
from core.test_utils import TestFactory


class CertificateAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level = self.factory.create_level(order=1)

    def _create_cert(self, **kwargs):
        defaults = {
            "student": self.profile,
            "level": self.level,
            "score": 80,
            "total_marks": 100,
        }
        defaults.update(kwargs)
        return Certificate.objects.create(**defaults)

    def test_list_empty(self):
        response = self.client.get("/api/v1/certificates/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_list_own_certificates(self):
        self._create_cert()
        response = self.client.get("/api/v1/certificates/")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["level_name"], self.level.name)

    def test_list_does_not_show_others(self):
        other_user, other_profile = self.factory.create_student(email="other@test.com")
        Certificate.objects.create(
            student=other_profile,
            level=self.level,
            score=90,
            total_marks=100,
        )
        response = self.client.get("/api/v1/certificates/")
        self.assertEqual(len(response.data), 0)

    def test_detail(self):
        cert = self._create_cert()
        response = self.client.get(f"/api/v1/certificates/{cert.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["certificate_number"], cert.certificate_number)
        self.assertEqual(response.data["student_name"], self.user.full_name)

    def test_detail_not_found(self):
        response = self.client.get("/api/v1/certificates/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_other_user_404(self):
        other_user, other_profile = self.factory.create_student(email="other2@test.com")
        level2 = self.factory.create_level(order=2)
        cert = Certificate.objects.create(
            student=other_profile,
            level=level2,
            score=70,
            total_marks=100,
        )
        response = self.client.get(f"/api/v1/certificates/{cert.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_certificate_number_auto_generated(self):
        cert = self._create_cert()
        self.assertTrue(cert.certificate_number.startswith("CERT-"))
        self.assertGreaterEqual(len(cert.certificate_number), 21)  # CERT- + 16 hex chars

    def test_unique_per_student_level(self):
        self._create_cert()
        with self.assertRaises((Exception,)):
            self._create_cert()

    def test_unauthenticated_denied(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.get("/api/v1/certificates/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminCertificateAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    def test_admin_list_all(self):
        Certificate.objects.create(
            student=self.profile,
            level=self.level,
            score=80,
            total_marks=100,
        )
        response = self.admin_client.get("/api/v1/certificates/admin/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_access_admin(self):
        student_client = self.factory.get_auth_client(self.user)
        response = student_client.get("/api/v1/certificates/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CertificateCollisionSafetyTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level1 = self.factory.create_level(order=1)
        self.level2 = self.factory.create_level(order=2)

    def test_certificate_number_length_increased(self):
        cert = Certificate.objects.create(
            student=self.profile,
            level=self.level1,
            score=80,
            total_marks=100,
        )
        self.assertTrue(cert.certificate_number.startswith("CERT-"))
        self.assertGreaterEqual(len(cert.certificate_number), 21)

    def test_certificate_numbers_unique_across_multiple(self):
        students = [self.factory.create_student(email=f"student{i}@test.com") for i in range(5)]
        levels = [self.factory.create_level(order=i + 10) for i in range(2)]

        certs = []
        for _idx, (_user, profile) in enumerate(students):
            for level in levels:
                cert = Certificate.objects.create(
                    student=profile,
                    level=level,
                    score=80,
                    total_marks=100,
                )
                certs.append(cert)

        certificate_numbers = [c.certificate_number for c in certs]
        self.assertEqual(len(certificate_numbers), len(set(certificate_numbers)))

    @mock.patch("apps.certificates.models.uuid.uuid4")
    def test_collision_retry_mechanism(self, mock_uuid4):
        # First call: create a certificate normally with a fixed UUID
        fixed_uuid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        different_uuid = uuid.UUID("11111111-2222-3333-4444-555555555555")

        mock_uuid4.return_value = fixed_uuid

        cert1 = Certificate.objects.create(
            student=self.profile,
            level=self.level1,
            score=80,
            total_marks=100,
        )

        # Second call: mock returns the same UUID twice (causing collisions),
        # then a different one on the third call
        mock_uuid4.side_effect = [fixed_uuid, fixed_uuid, different_uuid]

        cert2 = Certificate.objects.create(
            student=self.profile,
            level=self.level2,
            score=90,
            total_marks=100,
        )

        # Both certificates saved successfully with different numbers
        self.assertNotEqual(cert1.certificate_number, cert2.certificate_number)
        self.assertTrue(cert2.certificate_number.startswith("CERT-"))
