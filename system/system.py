import sys, socket

hostname = socket.gethostname()
if hostname == 'silence':
    ACHLYSBACKEND_PATH = '/home/achlys/AchlysBackEnd'
    START_JOB_PY_PATH = '%s/start_job.py' % ACHLYSBACKEND_PATH
    CHECK_JOB_PY_PATH = '%s/check_job.py' % ACHLYSBACKEND_PATH
else:
    print 'Unsupported system'
    sys.exit()

def get_png_dir(results_path):
    return results_path[0:-8] + '/PNG'

def get_pdb_dir(results_path):
    return results_path[0:-8] + '/PDB'

