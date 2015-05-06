# This file contains routines that the Achlys frontend uses start computational 
#    jobs and check the results of those jobs.
# These routines use django and rest_framework. They must be wired up to a 
#    django webserver. They expect to receive JSON in an HTTP request and 
#    return JSON in an HTTP response. (Some use query strings instead.) They 
#    read and store info in a database controlled by django. They call two 
#    python scripts (start_job.py and check_job.py) that do the actual work of 
#    starting and checking jobs.
# List of routines that should be wired up to URLS:
#    startjob
#    checkjob
#    company
#    employee
# The rest of the routines are supporting routines that are called by the 
#    four main routines.
#
# This code shouldn't know anything about how/where the computational job will
#    run except for only the paths to startjob.py and checkjob.py (currently in
#    backend.system) and the interfaces to those two scripts
#    Currently the code figures out the paths to the PNG and PDB directories by
#    inferring them from the path to results file stored in the database. But
#    this is ugly so I should figure out a cleaner way of doing this.

import os, os.path, json, csv, sys, urllib, \
        django.http, rest_framework.decorators, \
        backend.models, backend.struct_tools, backend.system

# These status strings are used for two purposes:
#   1. They are returned in the JSON to the frontend
#   2. They match strings that are returned by the start_job.py and 
#       check_job.py scripts
# They are also used for the status both for an entire job and for each
#   individual chemical structure (ligand) in a job
STATUS_DONE = 'DONE'
STATUS_RUNNING = 'RUNNING'
STATUS_STARTED = 'STARTED'
STATUS_ERROR = 'ERROR'

# Model IDs
MODEL_HERGKB1 = 'HERGKB1'
MODEL_DUMMY = 'DUMMY'
DEFAULT_MODEL = MODEL_DUMMY
SUPPORTED_MODELS = [MODEL_HERGKB1, MODEL_DUMMY]

# Read the results CSV file and return a JSON string representation
# results_file is the open results file
# png_dir is the path to the directory containing the chemical structures in 
#    PNG format
# pdb_dir is the path to the directory containing the final conformations in 
#    PDB format
def build_results_data_json(results_file, png_dir, pdb_dir, model_id_list):
    results_data_json_list = []
    results_reader = csv.reader(results_file)
    results_reader.next()
    chem_id = 1
    for row in results_reader:
        if chem_id > 1:
            results_data_json_list.append(' ,')
        results_data_json_list.append("{ ")
        results_data_json_list.append(' "chem_id" : %d ,' % chem_id)
        status = row[4]
        results_data_json_list.append(' "status" : "%s" ,' % status)
        results_data_json_list.append(' "error_message_list" : null ,')
        png_path = '%s/chem%d.png' % (png_dir, chem_id - 1)
        results_data_json_list.append(' "png_path" : "%s" ,' % png_path)
        png_base64 = urllib.quote(open(png_path, 'rb').read().encode('base64'))
        results_data_json_list.append(' "png_base64" : "%s" ,' % png_base64)
        results_data_json_list.append(' "chemical_name" : "%s" ,' % row[0])
        results_data_json_list.append(' "results" : [ ')
        model_count = 0
        for model_id in [MODEL_HERGKB1]:
            if model_count > 0:
                results_data_json_list.append(' , ')
            results_data_json_list.append(' { ')
            if status == STATUS_DONE:
                results_data_json_list.append(' "model_id" : "%s" ,' % model_id)
                results_data_json_list.append(' "prediction" : "%s" ,' % row[3])
                results_data_json_list.append(' "pIC50" : null ,')
                results_data_json_list.append(' "energy" : "%s" ,' % row[1])
                results_data_json_list.append(' "distance" : "%s" ,' % row[2])
                results_data_json_list.append(' "pdb_base64" : null ,')
                png_path = '%s/chem%d.png' % (png_dir, chem_id - 1)
                results_data_json_list.append(' "pdb_path" : "%s"' % png_path)
            else:
                results_data_json_list.append(' "model_id" : "%s" ,' % model_id)
                results_data_json_list.append(' "prediction" : null ,')
                results_data_json_list.append(' "pIC50" : null ,')
                results_data_json_list.append(' "energy" : null ,')
                results_data_json_list.append(' "distance" : null ,')
                results_data_json_list.append(' "pdb_path" : null ,')
                results_data_json_list.append(' "pdb_base64" : null')
            results_data_json_list.append(' }')
            model_count += 1
        results_data_json_list.append(' ]')
        results_data_json_list.append(" }")
        chem_id += 1
    return ''.join(results_data_json_list)

# Return the percent of structures that have been completed
# This could be improved further by figuring out what step each ligand is
#    currently running in
def get_percent_done(results_file, num_chems):
    results_reader = csv.reader(results_file)
    results_reader.next()
    results_data = []
    chem_id = 1
    done_count = 0
    for row in results_reader:
        status = row[4]
        if status == STATUS_DONE:
            done_count += 1
        chem_id += 1
    return float(done_count) / float(num_chems) * 100.0

# Return from startjob, sending json with an error message list
def return_startjob_error(error_message_list):
    error_message_string_list = []
    for i in xrange(0, len(error_message_list)):
        error_message_string_list.append('"%s"' % error_message_list[i])
        if i < len(error_message_list) - 1:
            error_message_string_list.append(' , ')
    error_message_string = ''.join(error_message_string_list)
    response_data_list = []
    response_data_list.append('{ ')
    response_data_list.append('"job_id" : null')
    response_data_list.append(' , ')
    response_data_list.append('"num_chems" : null')
    response_data_list.append(' , ')
    response_data_list.append('"status" : "ERROR"')
    response_data_list.append(' , ')
    response_data_list.append('"error_message_list" : [ %s ]' % 
            error_message_string)
    response_data_list.append = ' }' 
    response_data_string = ''.join(response_data_list)
    return django.http.HttpResponse(response_data_string)

# Return info about selected_jobs as a JSON string
# The info is: job_id, job_name, created_at, list of chemical_names
def build_job_info_json(selected_jobs):
    num_jobs = len(selected_jobs)
    job_list = []
    for job in selected_jobs.all():
        job_list.append(job)
    response_data_list = []
    response_data_list.append('{ "jobs" : [ ')
    for i in xrange(0, num_jobs):
        job = job_list[i]
        job_id = job.id
        created_at = job.created_at
        job_name = job.job_name
        chem_name_list = backend.struct_tools.get_chem_names(job.chem_lib_path)
        chem_name_string_list = []
        for j in xrange(0, len(chem_name_list)):
            chem_name = chem_name_list[j]
            chem_name_string_list.append('"%s"' % chem_name)
            if j < len(chem_name_list) - 1:
                chem_name_string_list.append(' , ')
        chem_name_string = ''.join(chem_name_string_list)
        response_data_list.append('{ ')
        response_data_list.append('"job_id" : %d' % job_id)
        response_data_list.append(' , ')
        response_data_list.append('"job_name" : "%s"' % job_name)
        response_data_list.append(' , ')
        response_data_list.append('"created_at" : "%s"' % created_at)
        response_data_list.append(' , ')
        response_data_list.append('"chemical_names" : [ %s ]' % 
                chem_name_string)
        response_data_list.append(' }')
        if i < num_jobs - 1:
            response_data_list.append(' , ')
    response_data_list.append(' ] }')
    response_data_string = ''.join(response_data_list)
    return response_data_string

def build_check_job_json(job_name, company_id, employee_id, num_chems, status, 
        error_message_list, percent_done, chems):
    response_data_list = []
    response_data_list.append('{ ')
    response_data_list.append('"job_name" : "%s"' % job_name)
    response_data_list.append(' , ')
    response_data_list.append('"companyId" : "%s"' % company_id)
    response_data_list.append(' , ')
    response_data_list.append('"employeeId" : "%s"' % employee_id)
    response_data_list.append(' , ')
    response_data_list.append('"num_chems" : "%d"' % num_chems)
    response_data_list.append(' , ')
    response_data_list.append('"status" : "%s"' % status)
    response_data_list.append(' , ')
    if error_message_list == None:
        response_data_list.append('"error_message_list" : null')
    else:
        error_message_list_list = []
        error_message_list_list.append('[ ')
        for error_i in xrange(0, len(error_message_list)):
            error_message = error_message_list[error_i]
            error_message_list_list.append('"%s"' % error_message)
            if error_i < len(error_message_list) - 1:
                error_message_list_list.append(' , ')
        error_message_list_list.append(' ]')
        error_message_list_string = ''.join(error_message_list_list)
        response_data_list.append('"error_message_list" : %s' % 
                error_message_list_string)
    response_data_list.append(' , ')
    response_data_list.append('"percent_done" : %s' % percent_done)
    response_data_list.append(' , ')
    if chems != None:
        response_data_list.append('"chems" : [ %s ]' % chems)
    else:
        response_data_list.append('"chems" : null')
    response_data_list.append(' }')
    response_data_string = ''.join(response_data_list)
    return response_data_string

# Start a job and return a job_id
# Expects at least a chem_lib_path passed in JSON request
# Optionally: model_id_list, companyId, employeeId, job_name
# Example
#    { "chem_lib_path" : "/home/achlys/CHEMLIBS/CR3/CR3_LP.sdf" , 
#      "model_id_list" : [ "DUMMY" ] , 
#      "companyId" : "3aac0f04-d715-4a69-8de0-c9166a313b23" , 
#      "employeeId" : "581869c9-7958-495b-a354-da81f86f525c" , 
#      "job_name" : "my_job_1" }
@rest_framework.decorators.api_view(['POST'])
def startjob(request):
    if request == None:
        return_startjob_error(['Request body missing'])
    request_json = json.loads(request.body)
    if not 'chem_lib_path' in request_json:
        return_startjob_error(['chem_lib_path missing'])
    chem_lib_path = request_json['chem_lib_path']
    if not os.path.isfile(chem_lib_path):
        return_startjob_error(['No file found at chem_lib_path: %s' % 
                chem_lib_path])
    if 'model_id_list' in request_json:
        model_id_list = request_json['model_id_list']
    else:
        model_id_list = [DEFAULT_MODEL]
    for model_id in model_id_list:
        if not model_id in SUPPORTED_MODELS:
            return_startjob_error(['Unsupported model: %s' % model_id])
    if 'companyId' in request_json:
        company_id = request_json['companyId']
    else:
        company_id = 'MISSING_COMPANY_ID'
    if 'employeeId' in request_json:
        employee_id = request_json['employeeId']
    else:
        employee_id = 'MISSING_EMPLOYEE_ID'
    if 'job_name' in request_json:
        job_name = request_json['job_name']
    else:
        job_name = 'UNNAMED_JOB'
    num_chems = backend.struct_tools.count_structs(chem_lib_path)
    new_job = backend.models.Job()
    new_job.chem_lib_path = chem_lib_path
    new_job.company_id = company_id
    new_job.employee_id = employee_id
    new_job.job_name = job_name
    new_job.save()
    job_id = new_job.id
    if not os.path.isfile(chem_lib_path):
        return_startjob_error(['No file found at chem_lib_path' % model_id])
    for model_id in model_id_list:
        cmd = 'python %s %d %s %s' % (backend.system.START_JOB_PY_PATH, job_id, 
                chem_lib_path, model_id)
        os.system(cmd)
    response_data_list = []
    response_data_list.append('{ ')
    response_data_list.append('"job_id" : "%d"' % job_id)
    response_data_list.append(' , ')
    response_data_list.append('"num_chems" : "%d"' % num_chems)
    response_data_list.append(' , ')
    response_data_list.append('"status" : "%s"' % STATUS_STARTED)
    response_data_list.append(' , ')
    response_data_list.append('"error_message_list" : null')
    response_data_list.append(' }')
    response_data_string = ''.join(response_data_list)
    return django.http.HttpResponse(response_data_string)

# Return info about a given job by job_id
# Expects a job_id in JSON request
# Example:
#     { "job_id" : "1" }
@rest_framework.decorators.api_view(['POST'])
def checkjob(request):
    request_json = json.loads(request.body)
    pk = request_json['job_id']
    try:
        job = backend.models.Job.objects.get(pk=pk)
    except backend.models.Job.DoesNotExist:
        return django.http.HttpResponse(status=404)
    company_id = job.company_id
    employee_id = job.employee_id
    job_name = job.job_name
    model_id_list = job.model_id_list
    num_chems = backend.struct_tools.count_structs(job.chem_lib_path)
    cmd = 'python %s %d' % (backend.system.CHECK_JOB_PY_PATH, int(pk))
    pipe = os.popen(cmd)
    if pipe == None:
        return django.http.HttpResponse(status=404)
    text = pipe.next()
    is_error = False
    if text.strip() == 'status=%s' % STATUS_ERROR:
        response_data = build_check_job_json(job_name, company_id, employee_id, 
                num_chems, STATUS_ERROR, ['The job is in an error state'], 
                'null')
    elif text.strip() == 'status=%s' % STATUS_RUNNING:
        response_data = build_check_job_json(job_name, company_id, employee_id, 
                num_chems, STATUS_RUNNING, ['The job is in an error state'], 
                'null', None)
        response_data = build_check_job_json(job_name, company_id, employee_id, 
                num_chems, STATUS_RUNNING, None, 0.0, None)
        text = pipe.next()
        if text != None and text.strip().startswith('results_path='):
            results_path = text.strip()[13:]
            try:
                results_file = open(results_path)
            except IOError:
                is_error = True
            if not is_error:
                png_dir = results_path[0:-8] + '/PNG'
                pdb_dir = results_path[0:-8] + '/PDB'
                results_data_json = build_results_data_json(results_file, 
                        png_dir, pdb_dir, model_id_list)
                results_file.close()
                try:
                    results_file = open(results_path)
                except IOError:
                    is_error = True
                if not is_error:
                    percent_done = get_percent_done(results_file, num_chems)
                    response_data = build_check_job_json(job_name, company_id, 
                            employee_id, num_chems, STATUS_RUNNING, None, 0.0,
                            results_data_json)
    elif text.strip() == 'status=%s' % STATUS_DONE:
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
                png_dir = backend.system.get_png_dir(results_path)
                pdb_dir = backend.system.get_pdb_dir(results_path)
                results_data_json = build_results_data_json(results_file, 
                        png_dir, pdb_dir, model_id_list)
                results_file.close()
                response_data = build_check_job_json(job_name, company_id, 
                            employee_id, num_chems, STATUS_DONE, None, 100.0,
                            results_data_json)
    else:
        is_error = True
    pipe_status = pipe.close()
    if pipe_status != None or is_error:
        response_data = build_check_job_json(job_name, company_id, employee_id, 
                num_chems, STATUS_ERROR, 
                ['There was an error checking the job status'], 'null')
        return django.http.HttpResponse(response_data)
    return django.http.HttpResponse(response_data)

# Return info about all jobs for a given companyId
# Must be called with Request Method = GET and with companyId in query string
# companyId is GUID (string)(
@rest_framework.decorators.api_view(['GET'])
def company(request):
    company_id = request.GET.get('companyId')
    selected_jobs = backend.models.Job.objects.filter(company_id=company_id)
    response_data_string = build_job_info_json(selected_jobs)
    return django.http.HttpResponse(response_data_string)

# Return info about all jobs for a given employeeId
# Must be called with Request Method = GET and with employeeId in query string
# employeeUd is GUID (string)(
@rest_framework.decorators.api_view(['GET'])
def employee(request):
    employee_id = request.GET.get('employeeId')
    selected_jobs = backend.models.Job.objects.filter(employee_id=employee_id)
    response_data_string = build_job_info_json(selected_jobs)
    return django.http.HttpResponse(response_data_string)

