from django.urls import path
from . import views

app_name = 'jasmin_config'

urlpatterns = [
    path('connectors/', views.connectors_list, name='connectors_list'),
    path('connectors/<str:cid>/<str:action>/', views.connector_action, name='connector_action'),
    path('groups/', views.groups_list, name='groups_list'),
    path('groups/<str:gid>/<str:action>/', views.group_action, name='group_action'),
    path('users/', views.users_list, name='users_list'),
    path('users/<str:uid>/<str:action>/', views.user_action, name='user_action'),
]