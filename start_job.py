import sys, os, os.path, socket, shutil, openbabel, pybel, lib.struct_tools

# Function to count the structures in an SDF file
def count_structs_sdf(chem_filename):
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

def count_structs_smi(chem_filename):
    smifile = open(chem_filename)
    struct_count = 0
    for line in smifile:
        line = line.strip()
        if line != '':
            struct_count += 1
    smifile.close()
    return struct_count

def count_structs(chem_filename):
    if chem_filename.endswith('.sdf'):
        return count_structs_sdf(chem_filename)
    elif chem_filename.endswith('.smi') or chem_filename.endswith('.txt'):
        return count_structs_smi(chem_filename)
    else:
        return 0


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
if len(sys.argv) < 3 or len(sys.argv) > 4:
    print 'Usage: %s job_id chem_path [model_id]' % (sys.argv[0])
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
if len(sys.argv) == 4:
    model_id = sys.argv[3]
if not model_id in ['HERGKB1', 'DUMMY']:
    print 'unknown model'
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
#if os.path.isdir(job_path):
#    print 'job_path already exists'
#    sys.exit()
if not os.path.isdir(job_path):
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

num_structs = count_structs(chem_path)
os.system('mkdir -p %s/PNG' % job_path)
#os.system('mkdir -p %s/PNG-%d' % (job_path, num_structs))
for i in xrange(0, num_structs):
    #os.system('mkdir -p %s/PNG-%d' % (job_path, i))
    #os.system('echo hi > PNG/chem%d.png' % i)
    os.system('babel -isdf %s -f%d -l%d -opng %s/PNG/chem%d.png' % (chem_path, i+1, i+1, job_path, i))


if model_id == 'HERGKB1':

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
        tox_sge_file.write('export PATH=/opt/namd/2.9/bin:$PATH\n')
        tox_sge_file.write('export PATH=/opt/openmpi/1.6/intel/bin:$PATH\n')
        tox_sge_file.write('export LD_LIBRARY_PATH=/opt/openmpi/1.6/intel/lib:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/compiler/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/mpirt/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/ipp/../compiler/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/ipp/lib/intel64:/opt/intel/mic/coi/host-linux-release/lib:/opt/intel/mic/myo/lib:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/compiler/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/mkl/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/tbb/lib/intel64/gcc4.4:$LD_LIBRARY_PATH\n')
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
        tox_sge_file.write('date\n')
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
        os.system('scp %s %s:%s' % ('/home/achlys/AchlysBackEnd/lib/struct_tools.py', REMOTE_USER, job_path))
        os.system('scp %s %s:%s' % (tox_sge_path, REMOTE_USER, job_path))
        os.system('scp %s %s:%s' % (tox_ini_path, REMOTE_USER, job_path))
        os.system('ssh %s "cd %s ; qsub tox.sge"' % (REMOTE_USER, job_path))

    else:

        print 'Unsupported system'
        sys.exit()

elif model_id == 'DUMMY':

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
        tox_sge_file.write('python tox.py %s/%s %s/out.csv \n' % (job_path, chem_filename, job_path))
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
        os.system('scp %s %s:%s' % ('/home/achlys/AchlysBackEnd/lib/struct_tools.py', REMOTE_USER, job_path))
        os.system('scp %s %s:%s' % (tox_sge_path, REMOTE_USER, job_path))
        os.system('scp %s %s:%s' % (tox_ini_path, REMOTE_USER, job_path))
        os.system('ssh %s "cd %s ; qsub tox.sge"' % (REMOTE_USER, job_path))

    else:

        print 'Unsupported system'
        sys.exit()
    
