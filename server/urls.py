from django.urls import path

from . import views


urlpatterns = [
    path('', views.index, name='server'),
    path('uapprove', views.uapprove, name='uapprove'),
    path('ulist', views.ulist, name='ulist'),
    path('doctype', views.doctype, name='doctype'),
    path('doccreate', views.doccreate, name='doccreate'),
    path('docedit', views.docedit, name='docedit'),
    path('doclist', views.doclist, name='doclist'),
    path('doclistro', views.doclist_readonly, name='doclistro'),
    path('docapprove', views.docapprove, name='docapprove'),
    path('docupload', views.upload_doc, name='docupload'),
    path('docpreview', views.docpreview, name='docpreview'),
    path('custom_parameters_preview', views.custom_parameters_preview, name='custom_parameters_preview'),
    path('progress', views.get_progress, name='progress'),
    path('request', views.data_request, name='request'),
    path('media/<int:id>/<str:t>/<str:flag>', views.media_request, name='media'),
]
