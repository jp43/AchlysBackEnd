import sys, os, socket, os.path

#TARGET_SYSTEM = 'local'
TARGET_SYSTEM = 'px'
REMOTE_USER = 'achlys@head.pharmamatrix.ualberta.ca'

# Function to run a shell command and return the output
def pipetext(cmd):
    pipe = os.popen(cmd)
    if pipe == None:
        print 'Pipe for command %s did not open' % cmd
        sys.exit()
    text = pipe.next()
    status = pipe.close()
    if status != None:
        print 'Command %s did not exit without errors' % cmd
        sys.exit()
    return text

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

# Assign system specific variables
hostname = socket.gethostname()
if hostname == 'turtle.local':
    local_job_base_path = '/Users/pwinter/Achlys/JOBS'
elif hostname == 'silence':
    local_job_base_path = '/home/achlys/JOBS'
else:
    print 'Unsupported system'
    sys.exit()

if TARGET_SYSTEM == 'local':

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

elif TARGET_SYSTEM == 'px':

    job_path = '/gluster/home/achlys/achlys/JOBS/%d' % job_id
    cmd = 'ssh %s "[ -d %s ] && echo Found || echo Notfound"' % (REMOTE_USER, job_path)
    if pipetext(cmd).strip() == 'Notfound':
        print 'job_path does not exist'
        sys.exit()
    else:
        cmd = 'ssh %s "[ -f %s/DONE ] && echo Found || echo Notfound"' % (REMOTE_USER, job_path)
        if pipetext(cmd).strip() == 'Found':
            print 'status=DONE'
            local_job_path = '%s/%d' % (local_job_base_path, job_id)
            if os.path.isdir(local_job_path):
                pass
                #print 'local_job_path already exists'
                #sys.exit()
            else:
                os.mkdir(local_job_path)
            os.system('scp %s:%s/out.csv %s' % (REMOTE_USER, job_path, local_job_path))
            print 'results_path=%s/out.csv' % local_job_path
        else:
            print 'status=RUNNING'
    
else:

    print 'Unsupported system'
    sys.exit()

