from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Include toàn bộ URL app core
    path('', include('core.urls')),
]
