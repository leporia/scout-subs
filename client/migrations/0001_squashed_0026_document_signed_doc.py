# Generated by Django 3.0.7 on 2020-07-30 08:46

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    replaces = [('client', '0001_initial'), ('client', '0002_usercode_user'), ('client', '0003_auto_20200619_1044'), ('client', '0004_auto_20200619_1045'), ('client', '0005_auto_20200619_1047'), ('client', '0006_auto_20200619_1049'), ('client', '0007_auto_20200619_1508'), ('client', '0008_auto_20200619_1538'), ('client', '0009_auto_20200619_1546'), ('client', '0010_documenttype_enabled'), ('client', '0011_keys'), ('client', '0012_document_group'), ('client', '0013_auto_20200620_1113'), ('client', '0014_auto_20200620_1506'), ('client', '0015_personaldata_email'), ('client', '0016_auto_20200620_1733'), ('client', '0017_usercode_medic'), ('client', '0018_auto_20200620_2007'), ('client', '0019_auto_20200620_2008'), ('client', '0020_auto_20200620_2200'), ('client', '0021_documenttype_sign_req'), ('client', '0022_auto_20200620_2316'), ('client', '0023_auto_20200622_1708'), ('client', '0024_auto_20200622_1930'), ('client', '0025_documenttype_custom_group'), ('client', '0026_document_signed_doc')]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0011_update_proxy_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('parent_name', models.CharField(default='', max_length=250)),
                ('via', models.CharField(default='', max_length=250)),
                ('cap', models.CharField(default='', max_length=250)),
                ('country', models.CharField(default='', max_length=250)),
                ('nationality', models.CharField(default='', max_length=250)),
                ('born_date', models.DateField(default=datetime.datetime(1970, 1, 1, 1, 0), null=True)),
                ('home_phone', models.CharField(default='', max_length=250)),
                ('phone', models.CharField(default='', max_length=250)),
                ('email', models.CharField(default='', max_length=250)),
            ],
        ),
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.IntegerField(default=0)),
                ('compilation_date', models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now)),
                ('document_type', models.CharField(default='', max_length=50)),
                ('status', models.CharField(default='', max_length=50)),
                ('user', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('personal_data', models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='client.PersonalData')),
            ],
            options={
                'permissions': [('approved', 'The user is approved')],
            },
        ),
        migrations.CreateModel(
            name='KeyVal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=240)),
                ('value', models.CharField(db_index=True, max_length=240)),
                ('container', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='client.Document')),
            ],
        ),
        migrations.CreateModel(
            name='DocumentType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group_private', models.BooleanField(default=False)),
                ('personal_data', models.BooleanField(default=False)),
                ('medical_data', models.BooleanField(default=False)),
                ('custom_data', models.BooleanField(default=False)),
                ('name', models.CharField(default='', max_length=250)),
                ('group', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('enabled', models.BooleanField(default=False)),
                ('custom_message', models.BooleanField(default=False)),
                ('custom_message_text', models.CharField(default='', max_length=250)),
                ('auto_sign', models.BooleanField(default=False)),
                ('custom_group', models.BooleanField(default=False)),
            ],
        ),
        migrations.AlterField(
            model_name='document',
            name='document_type',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='client.DocumentType'),
        ),
        migrations.CreateModel(
            name='Keys',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=240)),
                ('container', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='client.DocumentType')),
            ],
        ),
        migrations.AddField(
            model_name='document',
            name='group',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='auth.Group'),
        ),
        migrations.AlterField(
            model_name='document',
            name='personal_data',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.PROTECT, to='client.PersonalData'),
        ),
        migrations.CreateModel(
            name='MedicalData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('medic_name', models.CharField(default='', max_length=250)),
                ('address', models.CharField(default='', max_length=250)),
                ('allergy', models.CharField(default='', max_length=250)),
                ('cell_phone', models.CharField(default='', max_length=250)),
                ('drugs', models.CharField(default='', max_length=250)),
                ('drugs_bool', models.BooleanField(default=False)),
                ('emer_name', models.CharField(default='', max_length=250)),
                ('emer_phone', models.CharField(default='', max_length=250)),
                ('emer_relative', models.CharField(default='', max_length=250)),
                ('health_care', models.CharField(default='', max_length=250)),
                ('injuries', models.CharField(default='', max_length=250)),
                ('medic_address', models.CharField(default='', max_length=250)),
                ('medic_phone', models.CharField(default='', max_length=250)),
                ('misc', models.CharField(default='', max_length=250)),
                ('misc_bool', models.BooleanField(default=False)),
                ('rc', models.CharField(default='', max_length=250)),
                ('rega', models.BooleanField(default=False)),
                ('sickness', models.CharField(default='', max_length=250)),
                ('tetanus_date', models.DateField(default=datetime.datetime(1970, 1, 1, 1, 0), null=True)),
                ('vaccine', models.CharField(default='', max_length=250)),
                ('health_care_certificate', models.FileField(default=None, null=True, upload_to='documents/')),
                ('vac_certificate', models.FileField(null=True, upload_to='documents/')),
            ],
        ),
        migrations.AddField(
            model_name='document',
            name='medical_data',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.PROTECT, to='client.MedicalData'),
        ),
        migrations.CreateModel(
            name='UserCode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.IntegerField(default=0)),
                ('user', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('born_date', models.DateField(default=datetime.datetime(1970, 1, 1, 1, 0), null=True)),
                ('cap', models.CharField(default='', max_length=250)),
                ('country', models.CharField(default='', max_length=250)),
                ('home_phone', models.CharField(default='', max_length=250)),
                ('nationality', models.CharField(default='', max_length=250)),
                ('parent_name', models.CharField(default='', max_length=250)),
                ('phone', models.CharField(default='', max_length=250)),
                ('school', models.CharField(default='', max_length=250)),
                ('via', models.CharField(default='', max_length=250)),
                ('year', models.IntegerField(default=0)),
                ('medic', models.ForeignKey(default=None, on_delete=django.db.models.deletion.PROTECT, to='client.MedicalData')),
            ],
        ),
        migrations.AddField(
            model_name='document',
            name='signed_doc',
            field=models.FileField(default=None, null=True, upload_to='documents/'),
        ),
    ]