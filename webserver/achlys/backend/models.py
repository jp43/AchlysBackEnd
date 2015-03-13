from django.db import models

class Job(models.Model):
    chem_lib_path = models.TextField()
    job_path = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.job_id
