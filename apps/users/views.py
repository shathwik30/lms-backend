from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, status
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.levels.models import Level
from core.constants import ErrorMessage, SuccessMessage
from core.pagination import LargePagination
from core.permissions import IsAdmin
from core.throttling import SafeScopedRateThrottle

from .models import StudentProfile, UserPreference
from .serializers import (
    AdminStudentUpdateSerializer,
    ChangePasswordSerializer,
    GoogleAuthSerializer,
    IssueReportSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SendOTPSerializer,
    StudentProfileSerializer,
    UpdateProfileSerializer,
    UserPreferenceSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)
from .services import AuthService, PasswordResetService, ProfileService


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "login"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = AuthService.register(user)
        return Response(
            {"user": UserSerializer(user).data, "tokens": tokens},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: inline_serializer(
                "LoginResponse",
                fields={
                    "user": UserSerializer(),
                    "tokens": inline_serializer(
                        "TokenPair",
                        fields={
                            "refresh": drf_serializers.CharField(),
                            "access": drf_serializers.CharField(),
                        },
                    ),
                },
            )
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, tokens = AuthService.login(
            serializer.validated_data["email"],
            serializer.validated_data["password"],
        )
        if not user:
            return Response(
                {"detail": ErrorMessage.INVALID_CREDENTIALS},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"user": UserSerializer(user).data, "tokens": tokens})


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=GoogleAuthSerializer,
        responses={
            200: inline_serializer(
                "GoogleAuthResponse",
                fields={
                    "user": UserSerializer(),
                    "tokens": inline_serializer(
                        "GoogleTokenPair",
                        fields={
                            "refresh": drf_serializers.CharField(),
                            "access": drf_serializers.CharField(),
                        },
                    ),
                    "created": drf_serializers.BooleanField(),
                },
            )
        },
    )
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, tokens, result = AuthService.google_auth(
            serializer.validated_data["id_token"],
        )
        if not user:
            error_status = (
                status.HTTP_403_FORBIDDEN if result == ErrorMessage.ACCOUNT_DEACTIVATED else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": result}, status=error_status)

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": tokens,
                "created": result,
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                "MeResponse",
                fields={
                    "id": drf_serializers.IntegerField(),
                    "email": drf_serializers.EmailField(),
                    "full_name": drf_serializers.CharField(),
                    "phone": drf_serializers.CharField(),
                    "is_student": drf_serializers.BooleanField(),
                    "is_admin": drf_serializers.BooleanField(),
                    "profile": StudentProfileSerializer(required=False),
                },
            )
        }
    )
    def get(self, request):
        user = request.user
        data = UserSerializer(user).data
        if user.is_student and hasattr(user, "student_profile"):
            data["profile"] = StudentProfileSerializer(user.student_profile).data
        return Response(data)

    @extend_schema(request=UpdateProfileSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = UpdateProfileSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        user = ProfileService.update_profile(request.user, serializer.validated_data)
        return Response(UserSerializer(user).data)

    @extend_schema(
        request=None,
        responses={200: UserSerializer},
        description="Remove the current profile picture.",
    )
    def delete(self, request):
        user = ProfileService.remove_profile_picture(request.user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            "LogoutRequest",
            fields={
                "refresh": drf_serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                "LogoutResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                },
            )
        },
    )
    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response(
                {"detail": ErrorMessage.REFRESH_TOKEN_REQUIRED},
                status=status.HTTP_400_BAD_REQUEST,
            )
        success, message = AuthService.logout(token)
        if not success:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": message}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={
            200: inline_serializer(
                "ChangePasswordResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                },
            )
        },
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tokens, error = AuthService.change_password(
            request.user,
            serializer.validated_data["old_password"],
            serializer.validated_data["new_password"],
        )
        if error:
            return Response(
                {"old_password": [error]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "detail": SuccessMessage.PASSWORD_CHANGED,
                "refresh": tokens["refresh"],
                "access": tokens["access"],
            }
        )


# ── Admin views ──


class AdminStudentListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = StudentProfileSerializer
    pagination_class = LargePagination
    queryset = StudentProfile.objects.select_related(
        "user",
        "current_level",
        "highest_cleared_level",
    )
    filterset_fields = ["current_level", "highest_cleared_level"]
    search_fields = ["user__email", "user__full_name"]


class AdminStudentDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: StudentProfileSerializer})
    def get(self, request, pk):
        try:
            profile = StudentProfile.objects.select_related(
                "user",
                "current_level",
                "highest_cleared_level",
            ).get(pk=pk)
        except StudentProfile.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentProfileSerializer(profile).data)

    @extend_schema(request=AdminStudentUpdateSerializer, responses={200: StudentProfileSerializer})
    def patch(self, request, pk):
        try:
            profile = StudentProfile.objects.get(pk=pk)
        except StudentProfile.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminStudentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for field in ("current_level", "highest_cleared_level"):
            if field in serializer.validated_data:
                level_id = serializer.validated_data[field]
                if not Level.objects.filter(pk=level_id).exists():
                    return Response(
                        {"detail": f"Level {level_id} not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                setattr(profile, f"{field}_id", level_id)

        profile.save()
        return Response(StudentProfileSerializer(profile).data)


# ── Password Reset ──


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: inline_serializer(
                "PasswordResetRequestResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                },
            )
        },
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordResetService.request_reset(serializer.validated_data["email"])
        return Response({"detail": SuccessMessage.PASSWORD_RESET_SENT})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: inline_serializer(
                "PasswordResetConfirmResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                },
            )
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        success, message = PasswordResetService.confirm_reset(
            data["uid"],
            data["token"],
            data["new_password"],
        )
        if not success:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": message})


# ── OTP views ──


class SendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=SendOTPSerializer,
        responses={
            200: inline_serializer(
                "SendOTPResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                },
            )
        },
    )
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .otp import OTPService

        success, message = OTPService.send(
            serializer.validated_data["email"],
            serializer.validated_data["purpose"],
        )
        if not success:
            return Response({"detail": message}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        return Response({"detail": message})


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={
            200: inline_serializer(
                "VerifyOTPResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                    "verified": drf_serializers.BooleanField(),
                },
            )
        },
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .otp import OTPService

        success, message = OTPService.verify(
            serializer.validated_data["email"],
            serializer.validated_data["otp"],
            serializer.validated_data["purpose"],
        )
        if not success:
            return Response(
                {"detail": message, "verified": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": message, "verified": True})


# ── User Preferences ──


class UserPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserPreferenceSerializer})
    def get(self, request):
        prefs, _ = UserPreference.objects.get_or_create(user=request.user)
        return Response(UserPreferenceSerializer(prefs).data)

    @extend_schema(request=UserPreferenceSerializer, responses={200: UserPreferenceSerializer})
    def patch(self, request):
        prefs, _ = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(prefs, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ── Onboarding ──


class CompleteOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                "OnboardingResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                    "onboarding_completed": drf_serializers.BooleanField(),
                },
            )
        },
    )
    def post(self, request):
        success, error = ProfileService.complete_onboarding(request.user)
        if not success:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "detail": SuccessMessage.ONBOARDING_COMPLETED,
                "onboarding_completed": True,
            }
        )


# ── Report an Issue ──


class ReportIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=IssueReportSerializer, responses={201: IssueReportSerializer})
    def post(self, request):
        serializer = IssueReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IssueReportListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = IssueReportSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            from .models import IssueReport

            return IssueReport.objects.none()
        from .models import IssueReport

        return IssueReport.objects.filter(user=self.request.user)
