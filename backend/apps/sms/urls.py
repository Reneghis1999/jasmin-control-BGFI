from django.urls import path
from . import views

app_name = 'sms'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('send/', views.send_sms, name='send_sms'),
    path('dlr/', views.dlr_callback, name='dlr_callback'),
    path('list/', views.sms_list, name='sms_list'),
]