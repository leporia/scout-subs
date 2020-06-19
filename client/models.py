from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

# Create your models here.


class Document(models.Model):
    code = models.IntegerField(default=0)

    class Meta:
        permissions = [
            ("approved", "The user is approved")
        ]


class YearSubscription(models.Model):
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE)
    group = models.CharField(default="", max_length=50)
    compilation_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(default="", max_length=50)
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
