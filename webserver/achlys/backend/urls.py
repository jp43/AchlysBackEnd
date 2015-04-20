# Talk urls
from django.conf.urls import patterns, url
from backend import api

urlpatterns = patterns('',
    url(r'^api/v1/startjob/$', 'backend.api.startjob'),
    url(r'^api/v1/checkjob/$', 'backend.api.checkjob'),
)
