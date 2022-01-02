from django.urls import path, include

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('personal/', views.personal, name='personal'),
    path('terms/', views.terms, name='terms'),
    path('oauth_login/', views.oauth_login, name='oauth_login'),
    path('auth/', views.auth, name='auth'),
]
