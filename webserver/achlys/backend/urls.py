# Talk urls
from django.conf.urls import patterns, url
from backend import api

urlpatterns = patterns('',
    url(r'^api/v1/startjob/$', 'backend.api.startjob'),
    url(r'^api/v1/checkjob/$', 'backend.api.checkjob'),
    url(r'^api/v1/jobs/$', 'backend.api.job_collection'),
    url(r'^api/v1/jobs/(?P<pk>[0-9]+)$', 'backend.api.job_element'),
)
