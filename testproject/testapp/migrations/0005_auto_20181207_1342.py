# Generated by Django 2.1.3 on 2018-12-07 13:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testapp', '0004_auto_20181203_1104'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='points_max',
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='group',
            name='points_min',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
