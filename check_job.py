import sys, os, socket, os.path, lib.struct_tools

#TARGET_SYSTEM = 'local'
TARGET_SYSTEM = 'px'
REMOTE_USER = 'pwinter@head.pharmamatrix.ualberta.ca'

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
if len(sys.argv) != 3:
    print 'Usage: %s job_id model_id' % (sys.argv[0])
    sys.exit()
try:
    job_id = int(sys.argv[1])
except ValueError:
    print 'job_id must be an integer'
    sys.exit()
model_id = sys.argv[2]

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

    if model_id == 'DUMMY':

        job_path = '/nfs/r510-2/pwinter/achlys2/JOBS/%d' % job_id
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
                os.system('mkdir -p %s/PDB' % local_job_path)
                os.system('scp %s:%s/pdb/chem*.pdb %s/PDB/' % (REMOTE_USER, job_path, local_job_path))
                #os.system('mkdir -p %s/PNG' % local_job_path)
                #os.system('scp %s:%s/png/chem*.png %s/PNG/' % (REMOTE_USER, job_path, local_job_path))
                print 'results_path=%s/out.csv' % local_job_path
            else:
                print 'status=RUNNING'
                cmd = 'ssh %s "[ -f %s/out.csv ] && echo Found || echo Notfound"' % (REMOTE_USER, job_path)
                if pipetext(cmd).strip() == 'Found':
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
                    local_job_path = '%s/%d' % (local_job_base_path, job_id)
                    out_filename = '%s/out.csv' % local_job_path
                    out_file = open(out_filename, 'w')
                    out_file.write('Chemical Name,Energy,Distance,Prediction,STATUS\n')
                    #cmd = "ssh %s 'cat %s/chems.sdf | grep \"\'\"$$$$\"\'\" | wc -l'" % (REMOTE_USER, job_path)
                    #print cmd
                    #lig_count = int(pipetext(cmd).strip())
                    lig_count = 3
                    for lig_i in xrange(1, lig_count + 1):
                        chem_name = pipetext('ssh %s "babel -isdf %s/chems.sdf -f%d -l%d -otxt"' % (REMOTE_USER, job_path, lig_i, lig_i))
                        chem_name = chem_name.strip()
                        out_file.write('%s,NOT_AVAILABLE,NOT_AVAILABLE,NOT_AVAILABLE,RUNNING\n' % chem_name)
                    print 'results_path=%s/out.csv' % local_job_path
                    out_file.close()

    elif model_id == 'HERGKB1':
    
        job_path = '/nfs/r510-2/pwinter/achlys2/JOBS/%d' % job_id
        local_job_path = '%s/%d' % (local_job_base_path, job_id)
        if os.path.isdir(local_job_path):
            pass
            #print 'local_job_path already exists'
            #sys.exit()
        else:
            os.mkdir(local_job_path)
        cmd = 'ssh %s "[ -d %s ] && echo Found || echo Notfound"' % (REMOTE_USER, job_path)
        if pipetext(cmd).strip() == 'Notfound':
            print 'job_path does not exist'
            sys.exit()
        else:
            
            cmd = 'ssh %s "ls %s/results | wc -l"' % (REMOTE_USER, job_path)
            lig_count = int(pipetext(cmd).strip())
            
            out_filename = '%s/out.csv' % local_job_path
            out_file = open(out_filename, 'w')
            out_file.write('Chemical Name,Energy,Distance,Prediction,STATUS\n')
            
            done_count = 0
            for lig_i in xrange(0, lig_count):
            
                status_path = '%s/results/lig%d/status.txt' % (job_path, lig_i)
                cmd = 'ssh %s "[ -f %s ] && echo Found || echo Notfound"' % (REMOTE_USER, status_path)
        
                cmd_response = pipetext(cmd).strip()
                
                #print cmd
                #print cmd_response
        
                if cmd_response == 'Found':
                    
                    if os.path.isdir(local_job_path):
                        pass
                        #print 'local_job_path already exists'
                        #sys.exit()
                    else:
                        os.mkdir(local_job_path)
                    
                    cmd = 'ssh %s "cat %s"' % (REMOTE_USER, status_path)
                    pipe = os.popen(cmd)
                    if pipe == None:
                        print 'Could not open remote status file'
                        sys.exit()
                    text = pipe.next()
                    blocker_status = text.strip().split()[-1]
                    text = pipe.next()
                    distance = text.strip().split()[-1]
                    text = pipe.next()
                    binding_free_energy = text.strip().split()[-1]
                    pipe.close()
                    
                    if blocker_status == 'NON-BLOCKER':
                        blocker_status = 'Non-blocker'
                    elif blocker_status == 'BLOCKER':
                        blocker_status = 'Blocker'
                    
                    os.system('mkdir -p %s/PDB' % local_job_path)
                    os.system('scp %s:%s/results/lig%d/md-pose0/equ/end-equ.pdb %s/PDB/chem%d.pdb' % (REMOTE_USER, job_path, lig_i, local_job_path, lig_i))
                    #os.system('mkdir -p %s/PNG' % local_job_path)
                    #os.system('scp %s:%s/png/chem*.png %s/PNG/' % (REMOTE_USER, job_path, local_job_path))
                    
                    lig_pdb_first_line = pipetext('ssh %s "cat %s/results/lig%d/lig.pdb"' % (REMOTE_USER, job_path, lig_i))
                    chem_name = lig_pdb_first_line.strip().split()[1]
                    
                    out_file.write('%s,%s,%s,%s,DONE\n' % (chem_name, binding_free_energy, distance, blocker_status))

                    done_count += 1
                else:
                
                    lig_pdb_first_line = pipetext('ssh %s "cat %s/results/lig%d/lig.pdb"' % (REMOTE_USER, job_path, lig_i))
                    chem_name = lig_pdb_first_line.strip().split()[1]
                
                    out_file.write('%s,NOT_AVAILABLE,NOT_AVAILABLE,NOT_AVAILABLE,RUNNING\n' % chem_name)

            #print done_count
            #print lig_count

            if done_count == lig_count:
                print 'status=DONE'
            else:
                print 'status=RUNNING'
            print 'results_path=%s/out.csv' % local_job_path
            out_file.close()

    
    else:

        print 'Unsupported model'
        sys.exit()


else:

    print 'Unsupported system'
    sys.exit()

