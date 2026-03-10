from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import IssueReport, StudentProfile, UserPreference

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "password"]

    def create(self, validated_data):
        # StudentProfile is auto-created via post_save signal
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "profile_picture", "is_student", "is_admin"]
        read_only_fields = fields


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    current_level_name = serializers.CharField(source="current_level.name", default=None)
    highest_cleared_level_name = serializers.CharField(
        source="highest_cleared_level.name",
        default=None,
    )

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "user",
            "current_level",
            "current_level_name",
            "highest_cleared_level",
            "highest_cleared_level_name",
            "gender",
            "is_onboarding_completed",
            "is_onboarding_exam_attempted",
            "created_at",
        ]
        read_only_fields = fields


class AdminStudentUpdateSerializer(serializers.Serializer):
    current_level = serializers.IntegerField(required=False)
    highest_cleared_level = serializers.IntegerField(required=False)


class UpdateProfileSerializer(serializers.Serializer):
    MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024  # 5 MB

    full_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    profile_picture = serializers.ImageField(required=False, allow_empty_file=False)
    gender = serializers.ChoiceField(
        choices=StudentProfile.Gender.choices,
        required=False,
    )

    def validate_profile_picture(self, value):
        if value and value.size > self.MAX_PROFILE_PICTURE_SIZE:
            raise serializers.ValidationError(
                f"Profile picture must be under {self.MAX_PROFILE_PICTURE_SIZE // (1024 * 1024)} MB."
            )
        return value

    def validate_phone(self, value):
        if not value:
            return value
        user = self.context.get("user")
        qs = User.objects.filter(phone=value)
        if user:
            qs = qs.exclude(pk=user.pk)
        if qs.exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            "push_notifications",
            "email_notifications",
            "doubt_reply_notifications",
            "exam_result_notifications",
            "promotional_notifications",
        ]


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=["verify", "password_reset"],
        default="verify",
    )


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    purpose = serializers.ChoiceField(
        choices=["verify", "password_reset"],
        default="verify",
    )


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(help_text="Google ID token from client-side sign-in")


class IssueReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueReport
        fields = ["id", "category", "subject", "description", "screenshot", "is_resolved", "created_at"]
        read_only_fields = ["id", "is_resolved", "created_at"]
