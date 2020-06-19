# Generated by Django 3.0.7 on 2020-06-19 08:44

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('client', '0002_usercode_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='usercode',
            name='born_date',
            field=models.DateField(default=None),
        ),
        migrations.AddField(
            model_name='usercode',
            name='cap',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='country',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='home_phone',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='nationality',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='parent_name',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='phone',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='school',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='via',
            field=models.CharField(default='', max_length=250),
        ),
        migrations.AddField(
            model_name='usercode',
            name='year',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='YearSubscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.CharField(default='', max_length=50)),
                ('compilation_date', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(default='', max_length=50)),
                ('code', models.IntegerField(default=0)),
                ('parent_name', models.CharField(default='', max_length=250)),
                ('via', models.CharField(default='', max_length=250)),
                ('cap', models.CharField(default='', max_length=250)),
                ('country', models.CharField(default='', max_length=250)),
                ('nationality', models.CharField(default='', max_length=250)),
                ('born_date', models.DateField(default=None)),
                ('home_phone', models.CharField(default='', max_length=250)),
                ('phone', models.CharField(default='', max_length=250)),
                ('school', models.CharField(default='', max_length=250)),
                ('year', models.IntegerField(default=0)),
                ('user', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
