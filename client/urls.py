from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('create/<int:code>', views.create, name='create'),
    path('edit', views.edit, name='edit'),
    path('about', views.about, name='about'),
]
