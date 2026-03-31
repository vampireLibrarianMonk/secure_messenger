from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("messenger", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserNotificationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("dm_sound", models.CharField(choices=[("chime", "Chime"), ("pulse", "Pulse"), ("alert", "Alert"), ("soft", "Soft")], default="chime", max_length=32)),
                ("dm_document_sound", models.CharField(choices=[("chime", "Chime"), ("pulse", "Pulse"), ("alert", "Alert"), ("soft", "Soft")], default="pulse", max_length=32)),
                ("video_ring_sound", models.CharField(choices=[("chime", "Chime"), ("pulse", "Pulse"), ("alert", "Alert"), ("soft", "Soft")], default="alert", max_length=32)),
                ("chat_leave_sound", models.CharField(choices=[("chime", "Chime"), ("pulse", "Pulse"), ("alert", "Alert"), ("soft", "Soft")], default="soft", max_length=32)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="notification_preferences", to=settings.AUTH_USER_MODEL)),
            ],
            options={"abstract": False},
        ),
    ]