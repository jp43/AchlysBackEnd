import sys, os, socket, os.path

# Validate command line arguments
if len(sys.argv) != 2:
    print 'Usage: %s job_id' % (sys.argv[0])
    sys.exit()
try:
    job_id = int(sys.argv[1])
except ValueError:
    print 'job_id must be an integer'
    sys.exit()

# Assign system specific variables
hostname = socket.gethostname()
if hostname == 'turtle.local':
    job_base_path = '/Users/pwinter/Achlys/JOBS'
elif hostname == 'silence':
    job_base_path = '/home/achlys/JOBS'
else:
    print 'Unsupported system'
    sys.exit()

# Check if DONE file exists, return job status
job_path = '%s/%d' % (job_base_path, job_id)
if not os.path.isdir(job_path):
    print 'job_path does not exist'
    sys.exit()
if os.path.isfile('%s/DONE' % job_path):
    print 'status=DONE'
    print 'results_path=%s/out.csv' % job_path
else:
    print 'status=RUNNING'

