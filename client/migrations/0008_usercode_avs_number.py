# Generated by Django 3.1.4 on 2021-06-20 10:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0007_personaldata_avs_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='usercode',
            name='avs_number',
            field=models.CharField(default='', max_length=250),
        ),
    ]
