# Generated by Django 4.0 on 2022-01-01 05:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('triage', '0018_alter_tooldefect_managers_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='reported_dt',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]