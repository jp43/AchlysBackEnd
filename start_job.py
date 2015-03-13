import sys, os, os.path, socket, shutil

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
elif hostname == 'silence':
    job_base_path = '/home/achlys/JOBS'
    tox_script_path = '/home/achlys/AchlysBackEnd/tox.py'
else:
    print 'Unsupported system'
    sys.exit()

# Create job directory, copy tox.py to it, launch as background process
job_path = '%s/%d' % (job_base_path, job_id)
if os.path.isdir(job_path):
    print 'job_path already exists'
    sys.exit()
os.mkdir(job_path)
shutil.copyfile(tox_script_path, '%s/tox.py' % job_path)
os.chdir(job_path)
os.system('python tox.py %s %s/out.csv &' % (chem_path, job_path))

