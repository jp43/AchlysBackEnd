# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0003_auto_20150302_1900'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='chem_lib_path',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='job',
            name='created_at',
            field=models.DateTimeField(default=datetime.datetime(2015, 3, 3, 17, 10, 23, 833057, tzinfo=utc), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='job',
            name='job_path',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
