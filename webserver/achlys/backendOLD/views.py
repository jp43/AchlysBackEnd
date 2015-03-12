from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from backend.models import Job
from backend.serializers import JobSerializer


#def home(request):
#    tmpl_vars = {'form': PostForm()}
#    return render(request, 'talk/index.html', tmpl_vars)


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
