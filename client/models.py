from django.db import models
from django.contrib.auth.models import User, Group
from datetime import datetime

# Create your models here.


class DocumentType(models.Model):
    enabled = models.BooleanField(default=False)
    auto_sign = models.BooleanField(default=False)
    group_private = models.BooleanField(default=False)
    group = models.ForeignKey(Group, default=None, on_delete=models.CASCADE)
    custom_group = models.BooleanField(default=False)
    personal_data = models.BooleanField(default=False)
    medical_data = models.BooleanField(default=False)
    custom_data = models.BooleanField(default=False)
    custom_message = models.BooleanField(default=False)
    custom_message_text = models.CharField(default="", max_length=2048)
    staff_only = models.BooleanField(default=False)
    max_instances = models.IntegerField(default=0)
    name = models.CharField(default="", max_length=250)


class HideGroup(models.Model):
    group = models.ForeignKey(Group, default=None, on_delete=models.CASCADE)
    doc_type = models.ForeignKey(DocumentType, default=None, on_delete=models.CASCADE)


class PersonalData(models.Model):
    parent_name = models.CharField(default="", max_length=250)
    via = models.CharField(default="", max_length=250)
    cap = models.CharField(default="", max_length=250)
    country = models.CharField(default="", max_length=250)
    nationality = models.CharField(default="", max_length=250)
    born_date = models.DateField(null=True, default=datetime.fromtimestamp(0))
    home_phone = models.CharField(default="", max_length=250)
    phone = models.CharField(default="", max_length=250)
    email = models.CharField(default="", max_length=250)
    school = models.CharField(default="", max_length=250)
    year = models.IntegerField(default=0)
    avs_number = models.CharField(default="", max_length=250)


class MedicalData(models.Model):
    emer_name = models.CharField(default="", max_length=250)
    emer_relative = models.CharField(default="", max_length=250)
    cell_phone = models.CharField(default="", max_length=250)
    address = models.CharField(default="", max_length=250)
    emer_phone = models.CharField(default="", max_length=250)
    health_care = models.CharField(default="", max_length=250)
    injuries = models.CharField(default="", max_length=250)
    rc = models.CharField(default="", max_length=250)
    rega = models.BooleanField(default=False)
    medic_name = models.CharField(default="", max_length=250)
    medic_phone = models.CharField(default="", max_length=250)
    medic_address = models.CharField(default="", max_length=250)
    sickness = models.CharField(default="", max_length=250)
    vaccine = models.CharField(default="", max_length=250)
    tetanus_date = models.DateField(null=True, default=datetime.fromtimestamp(0))
    allergy = models.CharField(default="", max_length=250)
    drugs_bool = models.BooleanField(default=False)
    drugs = models.CharField(default="", max_length=250)
    misc_bool = models.BooleanField(default=False)
    misc = models.CharField(default="", max_length=250)
    vac_certificate = models.FileField(upload_to='documents/', null=True)
    health_care_certificate = models.FileField(default=None, upload_to='documents/', null=True)


class Keys(models.Model):
    container = models.ForeignKey(
        DocumentType, db_index=True, on_delete=models.CASCADE)
    key = models.CharField(max_length=2048, db_index=True)
    key_extra = models.CharField(max_length=2048, default="")


class UserCode(models.Model):
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE)
    medic = models.ForeignKey(MedicalData, default=None, on_delete=models.PROTECT)
    code = models.IntegerField(default=0)
    branca = models.ForeignKey(Group, default=None, on_delete=models.PROTECT, null=True)
    first_name = models.CharField(default="", max_length=250)
    last_name = models.CharField(default="", max_length=250)
    email = models.CharField(default="", max_length=250)
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
    avs_number = models.CharField(default="", max_length=250)
    midata_id = models.IntegerField(default=0)
    midata_token = models.CharField(default="", max_length=1024)


class Document(models.Model):
    usercode = models.ForeignKey(UserCode, default=None, on_delete=models.CASCADE)
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE, null=True)
    group = models.ForeignKey(Group, default=None, on_delete=models.CASCADE)
    code = models.IntegerField(default=0)
    compilation_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(default="", max_length=50)
    document_type = models.ForeignKey(
        DocumentType, default=None, on_delete=models.PROTECT)

    personal_data = models.ForeignKey(
        PersonalData, default=None, on_delete=models.PROTECT, null=True)

    medical_data = models.ForeignKey(
        MedicalData, default=None, on_delete=models.SET_NULL, null=True)

    signed_doc = models.FileField(default=None, upload_to='documents/', null=True)

    class Meta:
        permissions = [
            ("approved", "The user is approved"),
            ("staff", "The user is staff of the non primary group")
        ]


class KeyVal(models.Model):
    container = models.ForeignKey(
        Document, db_index=True, on_delete=models.CASCADE)
    key = models.CharField(max_length=2048, db_index=True)
    value = models.CharField(max_length=2048, db_index=True)


class GroupSettings(models.Model):
    group = models.ForeignKey(Group, default=None, on_delete=models.CASCADE)
    view_documents = models.BooleanField(default=False)
