# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0002_auto_20150302_1856'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='chem_lib_path',
            field=models.TextField(null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='job',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='job',
            name='job_path',
            field=models.TextField(null=True),
            preserve_default=True,
        ),
    ]
