# Generated by Django 3.0.7 on 2020-06-19 08:45

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0003_auto_20200619_1044'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usercode',
            name='born_date',
            field=models.DateField(default=datetime.datetime(2020, 6, 19, 10, 45, 47, 43395)),
        ),
        migrations.AlterField(
            model_name='yearsubscription',
            name='born_date',
            field=models.DateField(default=datetime.datetime(2020, 6, 19, 10, 45, 47, 42414)),
        ),
    ]
