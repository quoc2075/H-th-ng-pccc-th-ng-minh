from django.urls import path
from . import views


urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
  
    # Main Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Camera Stream - SỬA TÊN Ở ĐÂY
    path('camera_stream/', views.opencv_mjpeg_stream, name='opencv_mjpeg_stream'),
    
    # APIs
    path('api/pccc/data', views.api_pccc_data, name='api_pccc_data'),
    path('api/pccc/alert', views.api_pccc_alert, name='api_pccc_alert'),
    path('api/system/status', views.system_status_api, name='system_status_api'),
    
    # Device Control
    path('device/<int:device_id>/command/', views.device_command, name='device_command'),
    path('device/<int:device_id>/mode/', views.device_set_mode, name='device_set_mode'),
    
    # Admin Management
    path("dashboard/user/add/", views.admin_user_add, name="admin_user_add"),
    path("dashboard/user/<int:uid>/edit/", views.admin_user_edit, name="admin_user_edit"),
    path("dashboard/user/<int:uid>/delete/", views.admin_user_delete, name="admin_user_delete"),
    
    # Export
    path('export/events/', views.export_events_csv, name='export_events'),
    path('sse/alerts/', views.sse_alerts, name='sse_alerts'),   

    path("control/light/on/", views.light_on),
    path("control/light/off/", views.light_off),
    path("control/buzzer/on/", views.buzzer_on),
    path("control/buzzer/off/", views.buzzer_off),
    path('api/control/pump/on/', views.api_control_pump_on, name='api_pump_on'),
    path('api/control/pump/off/', views.api_control_pump_off, name='api_pump_off'),
    
    path('emergency/stop/', views.emergency_stop, name='emergency_stop'),
]