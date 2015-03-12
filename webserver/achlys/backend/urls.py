# Talk urls
from django.conf.urls import patterns, url
from backend import views

urlpatterns = patterns('',
    url(r'^api/v1/startjob/$', 'backend.views.startjob'),
    url(r'^api/v1/checkjob/$', 'backend.views.checkjob'),
    url(r'^api/v1/jobs/$', 'backend.views.job_collection'),
    url(r'^api/v1/jobs/(?P<pk>[0-9]+)$', 'backend.views.job_element'),
)
