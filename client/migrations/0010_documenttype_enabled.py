# Generated by Django 3.0.7 on 2020-06-19 16:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0009_auto_20200619_1546'),
    ]

    operations = [
        migrations.AddField(
            model_name='documenttype',
            name='enabled',
            field=models.BooleanField(default=False),
        ),
    ]