import os, os.path, json, csv, sys, urllib
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from backend.models import Job
from backend.serializers import JobSerializer

# Function to count the structures in an SDF file
def count_structs(chem_filename):
    struct_count = 0
    in_mol = True
    in_header = True
    in_data = False
    header_line_num = 0
    HEADER_LINES = 4
    sdfile = open(chem_filename)
    for line in sdfile:
        line = line.rstrip()
        if in_mol:
            if in_header:
                header_line_num += 1
                if header_line_num == HEADER_LINES:
                    in_header = False
            elif line == 'M  END':
                in_mol = False
        else:
            if line.startswith('>'):
                in_data = True
            elif in_data:
                if line == '':
                    in_data = False
            elif line == '$$$$':
                struct_count += 1
                in_mol = True
                in_header = True
                header_line_num = 0
    sdfile.close()
    return struct_count

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

def file_to_base64(path):
    encoded = urllib.quote(open(path, "rb").read().encode("base64"))
    return encoded


def build_results_data_json(results_file, num_chems, results_path):
    results_data_json = ''
    results_reader = csv.reader(results_file)
    results_reader.next()
    results_data = []
    chem_id = 1
    for row in results_reader:
        if chem_id > 1:
            results_data_json += ' ,'
        results_data_json += "{ "
        results_data_json += ' "chem_id" : %d ,' % chem_id
        status = row[4]
        results_data_json += ' "status" : "%s" ,' % status
        results_data_json += ' "error_message" : null ,'
        png_path = results_path[0:-8] + '/PNG/chem%d.png' % chem_id
        results_data_json += ' "png_path" : "%s" ,' % png_path
        results_data_json += ' "png_base64" : "%s" ,'  % file_to_base64(png_path)
        #results_data_json += ' "png_base64" : null ,'
        results_data_json += ' "chemical_name" : "%s" ,' % row[0]
        results_data_json += ' "results" : [ '
        model_count = 0
        for model_id in ['HERGKB1']:
            if model_count > 0:
                results_data_json += ' , '
            results_data_json += ' { '
            if status == 'DONE':
                results_data_json += ' "model_id" : "%s" ,' % model_id
                results_data_json += ' "prediction" : "%s" ,' % row[3]
                results_data_json += ' "pIC50" : null ,'
                results_data_json += ' "energy" : "%s" ,' % row[1]
                results_data_json += ' "distance" : "%s" ,' % row[2]
                pdb_path = results_path[0:-8] + '/PDB/chem%d.pdb' % chem_id
                results_data_json += ' "pdb_base64" : null ,'
                results_data_json += ' "pdb_path" : "%s"' % pdb_path
            else:
                results_data_json += ' "model_id" : "%s" ,' % model_id
                results_data_json += ' "prediction" : null ,'
                results_data_json += ' "pIC50" : null ,'
                results_data_json += ' "energy" : null ,'
                results_data_json += ' "distance" : null ,'
                results_data_json += ' "pdb_path" : null ,'
                results_data_json += ' "pdb_base64" : null'
            results_data_json += ' }'
            model_count += 1
            results_data_json += ' ]'
        results_data_json += " }"
        chem_id += 1
    return results_data_json

def get_percent_done(results_file, num_chems):
    results_reader = csv.reader(results_file)
    results_reader.next()
    results_data = []
    chem_id = 1
    done_count = 0
    for row in results_reader:
        status = row[4]
        if status == 'DONE':
            done_count += 1
        chem_id += 1
    #return 67.0
    return float(done_count) / float(num_chems) * 100.0

@api_view(['POST'])
def checkjob(request):
    request_body = request.body
    request_json = json.loads(request_body)
    pk = request_json['job_id']
    try:
        job = Job.objects.get(pk=pk)
    except Job.DoesNotExist:
        return HttpResponse(status=404)
    num_chems = count_structs(job.chem_lib_path)
    cmd = 'python %s %d' % (CHECK_JOB_PY_PATH, int(pk))
    pipe = os.popen(cmd)
    if pipe == None:
        return HttpResponse(status=404)
    text = pipe.next()
    is_error = False
    if text.strip() == 'status=ERROR':
        response_data = '{ "num_chems" : %d , "status" : "ERROR" , "error_message" : "The job is in an error state" , "percent_done" : null }' % num_chems
    elif text.strip() == 'status=RUNNING':
        response_data = '{ "num_chems" : %d , "status" : "RUNNING" , "error_message" : null , "percent_done" : 0.0 }' % num_chems
        text = pipe.next()
        if text != None and text.strip().startswith('results_path='):
            results_path = text.strip()[13:]
            try:
                results_file = open(results_path)
            except IOError:
                is_error = True
            if not is_error:
                results_data_json = build_results_data_json(results_file, num_chems, results_path)
                results_file.close()
                try:
                    results_file = open(results_path)
                except IOError:
                    is_error = True
                if not is_error:
                    percent_done = get_percent_done(results_file, num_chems)
                    response_data = '{ "num_chems" : %d , "status" : "RUNNING" , "error_message" : null , "percent_done" : %.1f , "chems" : [ %s ] }' % (num_chems, percent_done, results_data_json)
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
                results_data_json = build_results_data_json(results_file, num_chems, results_path)
                results_file.close()
                response_data = '{ "num_chems" : %d , "status" : "DONE" , "error_message" : null , "percent_done" : 100.0 , "chems" : [ %s ] }' % (num_chems, results_data_json)
    else:
        is_error = True
    pipe_status = pipe.close()
    if pipe_status != None or is_error:
        reponse_data = '{ "num_chems" : %d , "status" : "ERROR" , "error_message" : "There was an error checking the job status" , "percent_done" : null }'
        return HttpResponse(response_data)
    return HttpResponse(response_data)

@api_view(['POST'])
def startjob(request):
    if request == None:
        response_data = '{ "job_id" : null , "num_chems" : null , "status" : "ERROR" , "error_message" : "Request body missing" }'
        return HttpResponse(response_data)
    request_json = json.loads(request.body)
    if not 'chem_lib_path' in request_json:
        response_data = '{ "job_id" : null , "num_chems" : null , "status" : "ERROR" , "error_message" : "chem_lib_path missing" }'
        return HttpResponse(response_data)
    chem_lib_path = request_json['chem_lib_path']
    if 'model_id_list' in request_json:
        model_id_list = request_json['model_id_list']
    else:
        model_id_list = ['HERGKB1']
    for model_id in model_id_list:
        if not model_id in ['HERGKB1']:
            response_data = '{ "job_id" : null , "num_chems" : null , "status" : "ERROR" , "error_message" : "Unsupported model: %s" }' % model_id
            return HttpResponse(response_data)
    num_chems = count_structs(chem_lib_path)
    new_job = Job()
    new_job.chem_lib_path = chem_lib_path
    new_job.save()
    job_id = new_job.id
    if not os.path.isfile(chem_lib_path):
        response_data = '{ "job_id" : null , "num_chems" : null , "status" : "ERROR" , "error_message" : "No file found at chem_lib_path" }'
        return HttpResponse(response_data)
    cmd = 'python %s %d %s' % (START_JOB_PY_PATH, job_id, chem_lib_path)
    os.system(cmd)
    response_data = '{ "job_id" : "%d" , "num_chems" : %d , "status" : "STARTED" , "error_message" : null }' % (job_id, num_chems)
    return HttpResponse(response_data)

