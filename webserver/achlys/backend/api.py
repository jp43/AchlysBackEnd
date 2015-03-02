from tastypie.resources import ModelResource, Resource
from tastypie.constants import ALL
from tastypie import fields
from models import Job

class dict2obj(object):
    """
    Convert dictionary to object
    @source http://stackoverflow.com/a/1305561/383912
    """
    def __init__(self, d):
        self.__dict__['d'] = d
 
    def __getattr__(self, key):
        value = self.__dict__['d'][key]
        if type(value) == type({}):
            return dict2obj(value)
 
        return value
 

class CheckJob(ModelResource):
    class Meta:
        queryset = Job.objects.all()
        resource_name = 'checkjob'
        filtering = { "job_id" : ALL }

class StartJob(Resource):
    message = fields.CharField(attribute='message')

    class Meta:
        resource_name = 'startjob'

    def obj_get_list(self, request=None, **kwargs):
        posts = []
        posts.append(dict2obj({'message':'connection confirmed'}))
        return posts

