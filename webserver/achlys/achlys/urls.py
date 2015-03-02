from django.conf.urls import patterns, include, url
from tastypie.api import Api
from backend.api import CheckJob, StartJob
from django.contrib import admin

v1_api = Api(api_name='v1')
v1_api.register(CheckJob())
v1_api.register(StartJob())

urlpatterns = patterns('',
    url(r'^api/', include(v1_api.urls)),
    url(r'^admin/', include(admin.site.urls)),
)
