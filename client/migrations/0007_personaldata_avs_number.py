# Generated by Django 3.1.4 on 2021-06-20 10:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0006_documenttype_max_instances'),
    ]

    operations = [
        migrations.AddField(
            model_name='personaldata',
            name='avs_number',
            field=models.CharField(default='', max_length=250),
        ),
    ]
