import os, os.path, json, csv
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from backend.models import Job
from backend.serializers import JobSerializer

START_JOB_PY_PATH = '/home/achlys/AchlysBackEnd/start_job.py'
CHECK_JOB_PY_PATH = '/home/achlys/AchlysBackEnd/check_job.py'

def results_to_json(results_file):
    results_reader = csv.reader(results_file)
    results_list = []
    for row in results_reader:
        row_list = []
        for col in row:
            row_list.append(col)
        results_list.append(row_list)
    results_json = json.dumps(results_list)
    return results_json

@api_view(['POST'])
def checkjob(request):
    request_body = request.body
    request_json = json.loads(request_body)
    pk = request_json['job_id']
    try:
        job = Job.objects.get(pk=pk)
    except Job.DoesNotExist:
        return HttpResponse(status=404)
    cmd = 'python %s %d' % (CHECK_JOB_PY_PATH, int(pk))
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
            try:
                results_file = open(results_path)
            except IOError:
                is_error = True
            if not is_error:
                results_json = results_to_json(results_file)
                results_file.close()
                response_data = '"{ "status" : "DONE" , "results_path" : "%s" , "results_data" : %s }"' % (results_path, results_json)
    else:
        is_error = True
    pipe_status = pipe.close()
    if pipe_status != None or is_error:
        return HttpResponse(status=404)
    return HttpResponse(response_data)

@api_view(['POST'])
def startjob(request):
    request_json = json.loads(request.body)
    chem_lib_path = request_json['chem_lib_path']
    new_job = Job()
    new_job.chem_lib_path = chem_lib_path
    new_job.save()
    job_id = new_job.id
    if not os.path.isfile(chem_lib_path):
        return HttpResponse(status=404)
    cmd = 'python %s %d %s' % (START_JOB_PY_PATH, job_id, chem_lib_path)
    os.system(cmd)
    response_data = '{ "job_id" : "%d" }' % job_id
    return HttpResponse(response_data)

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

