#from tastypie.resources import ModelResource, Resource
#from tastypie.constants import ALL
#from tastypie.authentication import Authentication
#from tastypie.authorization import Authorization
#from tastypie import fields
from models import Job
import pdb

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
 

#class CheckJob(ModelResource):
#    status = fields.CharField(attribute='status')
#
#    class Meta:
#        resource_name = 'checkjob'
#        object_class = Job
#        authentication = Authentication()
#        authorization = Authorization()
#        queryset = Job.objects.all()
#        filtering = { 'id' : ALL }
#
#    def obj_get_list(self, request=None, **kwargs):
#        filtering = { "id" : request.GET('id') }
#        return self


#class StartJob(ModelResource):
#    #id = fields.IntegerField(attribute = 'id')
#    #chem_lib_path = fields.IntegerField(attribute = 'chem_lib_path')
#    #job_path = fields.CharField(attribute = 'job_path')
#    #created_at = fields.CharField(attribute = 'created_at')
#
#    class Meta:
#        resource_name = 'startjob'
#        object_class = Job
#        queryset = Job.objects.all()
#        filtering = { 'id' : ALL }
#        #list_allowed_methods = ['get', 'post']
#        #detail_allowed_methods = ['get', 'post', 'put', 'delete']
#        #authentication = Authentication()
#        #authorization = Authorization()
#
#    def obj_create(self, bundle, request=None, **kwargs):
#        pdb.set_trace()
#        print bundle
#        #bundle.obj = MyObject(kwargs)
#        #bundle = self.full_hydrate(bundle)
#        return bundle
#        #print 'my bundle.request()=', bundle.request()
#        #print kwargs
#        #path = bundle.data['chem_lib_path']
#        #j = Job(chem_lib_path=path, job_path='')
#        #j.save()
#        #j.job_path = '/home/achlys/JOBS/%s' % j.id
#        #j.save()
#        #return bundle

