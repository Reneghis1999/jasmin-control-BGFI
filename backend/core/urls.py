from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('apps.accounts.urls')),
    path('config/', include('apps.jasmin_config.urls')),
    path('sms/', include('apps.sms.urls')),
    path('', lambda request: redirect('sms:dashboard'), name='root_redirect'),
]