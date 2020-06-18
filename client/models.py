from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Document(models.Model):
    code = models.IntegerField(default=0)

    class Meta:
        permissions = [
            ("approved", "The user is approved")
        ]


class UserCode(models.Model):
    code = models.IntegerField(default=0)
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE)
