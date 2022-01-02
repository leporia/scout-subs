from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('personal/', views.personal, name='personal'),
    path('terms/', views.terms, name='terms'),
    path('oauth_login/', views.oauth_login, name='oauth_login'),
    path('auth/', views.auth, name='auth'),
    path('oauth_connect/', views.oauth_connect, name='oauth_connect'),
    path('auth_connect/', views.auth_connect, name='auth_connect'),
]
