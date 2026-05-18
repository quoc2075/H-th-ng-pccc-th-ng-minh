from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Device, Alert, EventLog

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = BaseUserAdmin.list_filter + ("role",)
    fieldsets = BaseUserAdmin.fieldsets + (
        (_("Role"), {"fields": ("role",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_("Role"), {"fields": ("role",)}),
    )

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "mqtt_topic_cmd", "mqtt_topic_stat", "mode_auto")
    list_filter = ("mode_auto",)
    search_fields = ("name", "mqtt_topic_cmd", "mqtt_topic_stat")

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("cls", "confidence", "created_at", "handled")
    list_filter = ("cls", "handled", "created_at")
    search_fields = ("cls",)

@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "category", "message")
    list_filter = ("category", "created_at")
    search_fields = ("message", "meta")
