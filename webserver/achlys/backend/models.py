from django.db import models

class Job(models.Model):
    job_name = models.TextField()
    chem_lib_path = models.TextField()
    job_path = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    company_id = models.TextField(default='NO_COMPANY_ID')
    employee_id = models.TextField(default='NO_EMPLOYEE_ID')
    model_id_list = models.TextField(default='["HERGKB1"]')

    def __unicode__(self):
        return self.job_id
