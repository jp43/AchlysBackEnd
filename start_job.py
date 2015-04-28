import sys, os, os.path, socket, shutil, openbabel, pybel


def do_prep_lig_sdf(chem_path, job_path):
    os.system('touch %s/DEBUG' % job_path)
    processed_chem_path = job_path + '/processed.sdf'
    #os.system('babel -isdf %s -ch --gen3D -osdf %s' % (chem_path, processed_chem_path))
    return processed_chem_path


def do_prep_lig_smi(chem_path, job_path):
    #mol = pybel.readfile('smi', chem_path)
    intermediate_chem_path = job_path + '/smi_to_sdf.sdf'
    #mol.write('sdf', intermediate_chem_path)
    os.system('babel -ismi %s -osdf %s' % (chem_path, intermediate_chem_path))
    os.system('touch %s/DEBUG1' % job_path)
    processed_chem_path = do_prep_lig_sdf(intermediate_chem_path, job_path)
    os.system('touch %s/DEBUG2' % job_path)
    #processed_chem_path = intermediate_chem_path
    return processed_chem_path


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
    tox_script_path = '/Users/pwinter/Achlys/git/AchlysBackEnd/achlys/kernel/tox.py'
    tox_sge_path = '/Users/pwinter/Achlys/git/AchlysBackEnd/tox.sge'
    tox_ini_path = '/Users/pwinter/Achlys/git/AchlysBackEnd/examples/config_PW.ini'
elif hostname == 'silence':
    job_base_path = '/home/achlys/JOBS'
    tox_script_path = '/home/achlys/AchlysBackEnd/achlys/kernel/tox.py'
    tox_sge_path = '/home/achlys/AchlysBackEnd/tox.sge'
    tox_ini_path = '/home/achlys/AchlysBackEnd/examples/config_PW.ini'
else:
    print 'Unsupported system'
    sys.exit()


# Create job dir on local system

job_path = '%s/%d' % (job_base_path, job_id)
if os.path.isdir(job_path):
    print 'job_path already exists'
    sys.exit()
os.mkdir(job_path)


## Prepare chemical input file
#
#if chem_path.endswith('.sdf'):
#
#    chem_path = do_prep_lig_sdf(chem_path, job_path)
#
#elif chem_path.endswith('.smi') or chem_path.endswith('.txt'):
#
#    chem_path = do_prep_lig_smi(chem_path, job_path)
#
#else:
#
#    print 'Unknown chemical file format'
#    sys.exit()

#print 'Done test'
#sys.exit()

def write_sge_file(tox_sge_path, chem_filename):
    tox_sge_file = open(tox_sge_path, 'w')
    tox_sge_file.write('#$ -N achlys\n')
    tox_sge_file.write('#$ -q achlys.q,parallel.q,serial.q\n')
    tox_sge_file.write('#$ -l h_rt=168:00:00\n')
    tox_sge_file.write('#$ -cwd\n')
    tox_sge_file.write('#$ -S /bin/bash\n')
    tox_sge_file.write('export PATH=/opt/mgltools/1.5.4/MGLToolsPckgs/AutoDockTools/Utilities24:$PATH\n')
    tox_sge_file.write('export PATH=/opt/autodock/4.2.3/bin:$PATH\n')
    tox_sge_file.write('export PATH=/gluster/home/achlys/achlys/bin:$PATH\n')
    tox_sge_file.write('export PYTHONPATH=/opt/mgltools/1.5.4/MGLToolsPckgs:$PYTHONPATH\n')
    tox_sge_file.write('export PYTHONPATH=/gluster/home/achlys/achlys/lib/python2.7/site-packages:$PYTHONPATH\n')
    tox_sge_file.write('export AMBERHOME=/pmshare/amber/amber12-20120918\n')
    tox_sge_file.write('export PATH=$AMBERHOME/bin:$PATH\n')
    tox_sge_file.write('python prepligs.py %s\n' % chem_filename)
    tox_sge_file.write('python /gluster/home/achlys/achlys/bin/tox \\\n')
    tox_sge_file.write('    -l pdb/* \\\n')
    for i in xrange(1, 46):
        if i == 1:
            tox_sge_file.write('    -r /gluster/home/achlys/achlys/data/KB_HERG/PDB/hERG-conformations_%02d.pdb \\\n' % i)
        else:
            tox_sge_file.write('    /gluster/home/achlys/achlys/data/KB_HERG/PDB/hERG-conformations_%02d.pdb \\\n' % i)
    tox_sge_file.write('    -n 8 \\\n')
    tox_sge_file.write('    --multi \\\n')
    tox_sge_file.write('    -f config_PW.ini\n')
    tox_sge_file.close()

if TARGET_SYSTEM == 'local':

    # Copy tox.py to job dir, launch as background process
    shutil.copyfile(tox_script_path, '%s/tox.py' % job_path)
    os.chdir(job_path)
    os.system('python tox.py %s %s/out.csv &' % (chem_path, job_path))

elif TARGET_SYSTEM == 'px':

    # Create job directory on remote server, copy chem file and tox.py to it, launch with qsub
    job_path = '/gluster/home/achlys/achlys/JOBS/%d' % job_id
    os.system('ssh %s "mkdir %s"' % (REMOTE_USER, job_path))
    chem_filename = os.path.basename(chem_path)
    os.system('scp %s %s:%s/%s' % (chem_path, REMOTE_USER, job_path, chem_filename))
    os.system('scp %s %s:%s' % (tox_script_path, REMOTE_USER, job_path))
    local_job_path = '%s/%d' % (job_base_path, job_id)
    tox_sge_path = local_job_path + '/tox.sge'
    write_sge_file(tox_sge_path, chem_filename)
    prepligs_path = '/home/achlys/AchlysBackEnd/prepligs.py'
    os.system('scp %s %s:%s' % (prepligs_path, REMOTE_USER, job_path))
    os.system('scp %s %s:%s' % (tox_sge_path, REMOTE_USER, job_path))
    os.system('scp %s %s:%s' % (tox_ini_path, REMOTE_USER, job_path))
    os.system('ssh %s "cd %s ; qsub tox.sge"' % (REMOTE_USER, job_path))

else:

    print 'Unsupported system'
    sys.exit()

