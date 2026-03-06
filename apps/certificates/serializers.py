from rest_framework import serializers

from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    student_email = serializers.CharField(source="student.user.email", read_only=True)
    level_name = serializers.CharField(source="level.name", read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "id",
            "student",
            "student_name",
            "student_email",
            "level",
            "level_name",
            "certificate_number",
            "issued_at",
            "certificate_url",
            "score",
            "total_marks",
        ]
        read_only_fields = fields
