# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='job',
            name='chem_lib_path',
        ),
        migrations.RemoveField(
            model_name='job',
            name='created_at',
        ),
        migrations.RemoveField(
            model_name='job',
            name='job_id',
        ),
    ]
