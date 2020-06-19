from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='server'),
    path('uapprove', views.uapprove, name='uapprove'),
    path('ulist', views.ulist, name='ulist'),
    path('doctype', views.doctype, name='doctype'),
    path('docedit', views.docedit, name='docedit'),
    path('doclist', views.doclist, name='doclist'),
]
