from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('approve', views.approve, name='approve'),
    path('create', views.create, name='create'),
    path('edit', views.edit, name='edit'),
]
