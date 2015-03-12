import os, os.path, json
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from backend.models import Job
from backend.serializers import JobSerializer


def home(request):
    return render(request, 'jobs/index.html', None)


@api_view(['GET'])
def job_collection(request):
    if request.method == 'GET':
        jobs = Job.objects.all()
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data)


@api_view(['GET'])
def job_element(request, pk):
    try:
        job = Job.objects.get(pk=pk)
    except Job.DoesNotExist:
        return HttpResponse(status=404)

    if request.method == 'GET':
        serializer = JobSerializer(job)
        return Response(serializer.data)

@api_view(['POST'])
def checkjob(request):
    request_body = request.body
    request_json = json.loads(request_body)
    pk = request_json['job_id']

    try:
        job = Job.objects.get(pk=pk)
    except Job.DoesNotExist:
        return HttpResponse(status=404)

    if request.method == 'POST':
        cmd = 'python /home/achlys/AchlysBackEnd/check_job.py %d' % int(pk)
        pipe = os.popen(cmd)
        if pipe == None:
            return HttpResponse(status=404)
        text = pipe.next()
        is_error = False
        if text.strip() == 'status=ERROR':
            response_data = '{ "status" : "ERROR" }'
        elif text.strip() == 'status=RUNNING':
            response_data = '{ "status" : "RUNNING" }'
        elif text.strip() == 'status=DONE':
            text = pipe.next()
            if not text.strip().startswith('results_path='):
                is_error = True
            else:
                results_path = text.strip()[13:]
                response_data = '"{ "status" : "DONE" , "results_path" : "%s" }"' % results_path
        else:
            is_error = True
        pipe_status = pipe.close()
        if pipe_status != None:
            return HttpResponse(status=404)
        if is_error:
            return HttpResponse(status=404)
        return HttpResponse(response_data)

@api_view(['POST'])
def startjob(request):
    #response_data = '{ "status" : "trying startjob" }'
    request_body = request.body
    request_json = json.loads(request_body)
    chem_lib_path = request_json['chem_lib_path']
    new_job = Job()
    new_job.chem_lib_path = chem_lib_path
    new_job.save()
    job_id = new_job.id
    if not os.path.isfile(chem_lib_path):
        return HttpResponse(status=404)
    cmd = 'python /home/achlys/AchlysBackEnd/start_job.py %d %s' % (job_id, chem_lib_path)
    os.system(cmd)
    #pipe = os.popen(cmd)
    #if pipe == None:
    #    return HttpResponse(status=404)
    #pipe_status = pipe.close()
    #if pipe_status != None:
    #    return HttpResponse(status=404)
    response_data = '{ "job_id" : "%d" }' % job_id
    return HttpResponse(response_data)

#from talk.models import Post
#from talk.forms import PostForm
#from talk.serializers import PostSerializer
#from rest_framework import generics
#from django.shortcuts import render
#
#
#def home(request):
#    tmpl_vars = {'form': PostForm()}
#    return render(request, 'talk/index.html', tmpl_vars)
#
#
##########################
#### class based views ###
##########################
#
#class PostCollection(generics.ListCreateAPIView):
#    queryset = Post.objects.all()
#    serializer_class = PostSerializer
#
#
#class PostMember(generics.RetrieveDestroyAPIView):
#    queryset = Post.objects.all()
#    serializer_class = PostSerializer

# class PostCollection(mixins.ListModelMixin,
#                      mixins.CreateModelMixin,
#                      generics.ListAPIView):

#     queryset = Post.objects.all()
#     serializer_class = PostSerializer

#     def get(self, request, *args, **kwargs):
#         return self.list(request, *args, **kwargs)

#     def post(self, request, *args, **kwargs):
#         return self.create(request, *args, **kwargs)


# class PostMember(mixins.RetrieveModelMixin,
#                  mixins.DestroyModelMixin,
#                  generics.GenericAPIView):

#     queryset = Post.objects.all()
#     serializer_class = PostSerializer

#     def get(self, request, *args, **kwargs):
#         return self.retrieve(request, *args, **kwargs)

#     def delete(self, request, *args, **kwargs):
#         return self.destroy(request, *args, **kwargs)

############################
### function based views ###
############################

# from django.shortcuts import get_object_or_404
# from rest_framework.decorators import api_view
# from rest_framework.response import Response
# from rest_framework import status
# from talk.models import Post
# from talk.serializers import PostSerializer

# @api_view(['GET', 'POST'])
# def post_collection(request):
#     if request.method == 'GET':
#         posts = Post.objects.all()
#         serializer = PostSerializer(posts, many=True)
#         return Response(serializer.data)
#     elif request.method == 'POST':
#         data = {'text': request.DATA.get('the_post'), 'author': request.user}
#         serializer = PostSerializer(data=data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# @api_view(['GET', 'DELETE'])
# def post_element(request, pk):

#     post = get_object_or_404(Post, id=pk)

#     # try:
#     #     post = Post.objects.get(pk=pk)
#     # except Post.DoesNotExist:
#     #     return HttpResponse(status=404)

#     if request.method == 'GET':
#         serializer = PostSerializer(post)
#         return Response(serializer.data)

#     elif request.method == 'DELETE':
#         post.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)
