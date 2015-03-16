import sys, os, os.path, socket, shutil

#TARGET_SYSTEM = 'local'
TARGET_SYSTEM = 'px'
REMOTE_USER = 'achlys@head.pharmamatrix.ualberta.ca'

# Validate command line arguments
if len(sys.argv) != 3:
    print 'Usage: %s job_id chem_path' % (sys.argv[0])
    sys.exit()
try:
    job_id = int(sys.argv[1])
except ValueError:
    print 'job_id must be an integer'
    sys.exit()
chem_path = sys.argv[2]
if not os.path.isfile(chem_path):
    print 'chem_path not found'
    sys.exit()

# Assign system specific variables
hostname = socket.gethostname()
if hostname == 'turtle.local':
    job_base_path = '/Users/pwinter/Achlys/JOBS'
    tox_script_path = '/Users/pwinter/Achlys/git/AchlysBackEnd/tox.py'
    tox_sge_path = '/Users/pwinter/Achlys/git/AchlysBackEnd/tox.sge'
elif hostname == 'silence':
    job_base_path = '/home/achlys/JOBS'
    tox_script_path = '/home/achlys/AchlysBackEnd/tox.py'
    tox_sge_path = '/home/achlys/AchlysBackEnd/tox.sge'
else:
    print 'Unsupported system'
    sys.exit()

if TARGET_SYSTEM == 'local':

    # Create job directory, copy tox.py to it, launch as background process
    job_path = '%s/%d' % (job_base_path, job_id)
    if os.path.isdir(job_path):
        print 'job_path already exists'
        sys.exit()
    os.mkdir(job_path)
    shutil.copyfile(tox_script_path, '%s/tox.py' % job_path)
    os.chdir(job_path)
    os.system('python tox.py %s %s/out.csv &' % (chem_path, job_path))

elif TARGET_SYSTEM == 'px':

    # Create job directory on remote server, copy chem file and tox.py to it, launch with qsub
    job_path = '/gluster/home/achlys/achlys/JOBS/%d' % job_id
    os.system('ssh %s "mkdir %s"' % (REMOTE_USER, job_path))
    os.system('scp %s %s:%s/chems.sdf' % (chem_path, REMOTE_USER, job_path))
    os.system('scp %s %s:%s' % (tox_script_path, REMOTE_USER, job_path))
    os.system('scp %s %s:%s' % (tox_sge_path, REMOTE_USER, job_path))
    os.system('ssh %s "cd %s ; qsub tox.sge"' % (REMOTE_USER, job_path))

else:
    print 'Unsupported system'
    sys.exit()

