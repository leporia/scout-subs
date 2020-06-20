from django.db import models
from django.contrib.auth.models import User, Group
from datetime import datetime

# Create your models here.


class DocumentType(models.Model):
    enabled = models.BooleanField(default=False)
    group_private = models.BooleanField(default=False)
    group = models.ForeignKey(Group, default=None, on_delete=models.CASCADE)
    personal_data = models.BooleanField(default=False)
    medical_data = models.BooleanField(default=False)
    custom_data = models.BooleanField(default=False)
    custom_message = models.BooleanField(default=False)
    custom_message_text = models.CharField(default="", max_length=250)
    name = models.CharField(default="", max_length=250)


class PersonalData(models.Model):
    parent_name = models.CharField(default="", max_length=250)
    via = models.CharField(default="", max_length=250)
    cap = models.CharField(default="", max_length=250)
    country = models.CharField(default="", max_length=250)
    nationality = models.CharField(default="", max_length=250)
    born_date = models.DateField(null=True, default=datetime.fromtimestamp(0))
    home_phone = models.CharField(default="", max_length=250)
    phone = models.CharField(default="", max_length=250)


class Document(models.Model):
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, default=None, on_delete=models.CASCADE)
    code = models.IntegerField(default=0)
    compilation_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(default="", max_length=50)
    document_type = models.ForeignKey(
        DocumentType, default=None, on_delete=models.PROTECT)

    personal_data = models.ForeignKey(
        PersonalData, default=None, on_delete=models.PROTECT, null=True)

    class Meta:
        permissions = [
            ("approved", "The user is approved")
        ]


class KeyVal(models.Model):
    container = models.ForeignKey(
        Document, db_index=True, on_delete=models.CASCADE)
    key = models.CharField(max_length=240, db_index=True)
    value = models.CharField(max_length=240, db_index=True)


class Keys(models.Model):
    container = models.ForeignKey(
        DocumentType, db_index=True, on_delete=models.CASCADE)
    key = models.CharField(max_length=240, db_index=True)


class UserCode(models.Model):
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE)
    code = models.IntegerField(default=0)
    parent_name = models.CharField(default="", max_length=250)
    via = models.CharField(default="", max_length=250)
    cap = models.CharField(default="", max_length=250)
    country = models.CharField(default="", max_length=250)
    nationality = models.CharField(default="", max_length=250)
    born_date = models.DateField(null=True, default=datetime.fromtimestamp(0))
    home_phone = models.CharField(default="", max_length=250)
    phone = models.CharField(default="", max_length=250)
    school = models.CharField(default="", max_length=250)
    year = models.IntegerField(default=0)
