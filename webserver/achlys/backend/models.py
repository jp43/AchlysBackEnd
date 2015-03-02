from django.db import models

# Create your models here.
class Job(models.Model):
    job_id = models.CharField(max_length=200)
    chem_lib_path = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.job_id
