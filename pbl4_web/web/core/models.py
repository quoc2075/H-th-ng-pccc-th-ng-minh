from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    # 🔥 THÊM FIELD NÀY
    can_view_cam = models.BooleanField(default=True)

class Device(models.Model):
    name = models.CharField(max_length=100)
    mqtt_topic_cmd = models.CharField(max_length=200)
    mqtt_topic_stat = models.CharField(max_length=200)
    mode_auto = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Alert(models.Model):
    cls = models.CharField(max_length=50)
    confidence = models.FloatField(default=0)

    x1 = models.IntegerField(null=True, blank=True)
    y1 = models.IntegerField(null=True, blank=True)
    x2 = models.IntegerField(null=True, blank=True)
    y2 = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    handled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cls} ({self.confidence:.2f})"

class EventLog(models.Model):
    category = models.CharField(max_length=50)
    message = models.CharField(max_length=255)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"[{self.category}] {self.message}"
