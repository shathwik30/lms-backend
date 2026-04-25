from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="studentprofile",
            name="is_onboarding_exam_attempted",
        ),
    ]
