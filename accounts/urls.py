from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('personal/', views.personal, name='personal'),
    path('edit/<int:code>', views.edit, name='edit_user'),
    path('terms/', views.terms, name='terms'),
    path('oauth_login/', views.oauth_login, name='oauth_login'),
    path('auth/', views.auth, name='auth'),
    path('oauth_connect/', views.oauth_connect, name='oauth_connect'),
    path('oauth_disconnect/', views.oauth_disconnect, name='oauth_disconnect'),
    path('auth_connect/', views.auth_connect, name='auth_connect'),
    path('user_switcher/', views.user_switcher, name='user_switcher'),
]
