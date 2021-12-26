from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('personal/', views.personal, name='personal'),
    path('terms/', views.terms, name='terms'),
]
