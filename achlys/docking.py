from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

def write_docking_job_array(script_name, ncpus, config_file, queue='achlys.q'):

    jobname = os.path.splitext(script_name)[0]

    with open(script_name, 'w') as file:
        script ="""#$ -N %(jobname)s
#$ -q %(queue)s
#$ -l h_rt=168:00:00
#$ -t 1-%(ncpus)s:1
#$ -V
#$ -cwd
#$ -S /bin/bash

cd target$((SGE_TASK_ID-1))

python ../docking.py -f ../%(config_file)s
echo $? > status.txt
"""% locals()
        file.write(script)

def submit_docking_job(jobid, nligs, ntargets, submit_on='pharma'):

    # the following path is supposed to exist on the remote machine
    remote_path = 'tmp/results'
    workdir = 'job_' + jobid

    remote_dir = remote_path + '/' + workdir

    fh, tmp = tempfile.mkstemp(suffix='.sh')

    with open(tmp, 'w') as file:
        script ="""cd %(remote_path)s
rm -rf %(workdir)s
mkdir %(workdir)s
cd %(workdir)s

# make directory
mkdir ligs
mkdir targets
"""% locals()
        file.write(script)

    # create results directory on the remote machine (pharma)
    subprocess.call("ssh pharma 'bash -s' < " + tmp, shell=True)
    # secure copy ligand files
    subprocess.call("scp lig*/lig*.pdb pharma:%s/ligs"%remote_dir, shell=True)
    # secure copy receptor files
    subprocess.call("scp targets/* pharma:%s/targets/"%remote_dir, shell=True)

    script_name = 'run_docking.sge'
    write_docking_job_array(script_name, ntargets, 'config.ini')
    achlysdir = os.path.realpath(__file__)
    py_docking_script  = '/'.join(achlysdir.split('/')[:-1]) + '/kernel/docking.py'

    subprocess.call("scp config.ini run_docking.sge %s pharma:%s/"%(py_docking_script,remote_dir), shell=True)
    time.sleep(5) # wait 5 sec to avoid freezing when using many scp's

    shutil.rmtree('run_docking.sge', ignore_errors=True)

    # (A) prepare docking jobs
    fh, tmp = tempfile.mkstemp(suffix='.sh')
    with open(tmp, 'w') as file:
        script ="""source ~/.bash_profile
cd %(remote_dir)s

for lig_id in `seq 1 %(nligs)s`; do
  # prepare files for docking 
  mkdir lig$((lig_id-1))

  cp config.ini run_docking.sge docking.py lig$((lig_id-1))/
  for target_id in `seq 1 %(ntargets)s`; do
    mkdir lig$((lig_id-1))/target$((target_id-1))
    cp ligs/lig$((lig_id-1)).pdb lig$((lig_id-1))/target$((target_id-1))/lig.pdb
    cp targets/target$((target_id-1)).pdb lig$((lig_id-1))/target$((target_id-1))/target.pdb
  done
done

# clean up work directory
rm -rf ligs targets config.ini run_docking.sge docking.py
"""% locals()
        file.write(script)

    subprocess.call("ssh pharma 'bash -s' < " + tmp, shell=True)

    # (B) submit docking jobs
    fh, tmp = tempfile.mkstemp(suffix='.sh')
    with open(tmp, 'w') as file:
        script ="""source ~/.bash_profile
cd %(remote_dir)s

# submit jobs
for lig_id in `seq 1 %(nligs)s`; do
  cd lig$((lig_id-1))

  jobID=`qsub run_docking.sge` # submit job

  jobID=`echo $jobID | awk 'match($0,/[0-9]+/){print substr($0, RSTART, RLENGTH)}'` # check job ID
  echo $jobID > jobID # save jobID inside a file
  cd ..
done
"""% locals()
        file.write(script)

    subprocess.call("ssh pharma 'bash -s' < " + tmp, shell=True)
    return 'running'

def write_check_docking_script(remote_dir, ligs_idxs):
    ligs_idxs_bash = ' '.join(map(str,ligs_idxs))

    fh, tmp = tempfile.mkstemp(suffix='.sh')
    with open(tmp, 'w') as file:
        script ="""source ~/.bash_profile
cd %(remote_dir)s

for lig_id in %(ligs_idxs_bash)s; do
  cd lig$lig_id
  for target_id in `seq 1 %(ntargets)s`; do
    if [ -f target$((target_id-1))/status.txt ]; then
      echo `cat target$((target_id-1))/status.txt`
    else
      echo -1
    fi
  done 
  echo
  cd ..
done
"""% locals()
        file.write(script)
    return tmp

def get_docking_status(output):

    output = output.split('\n')[:-1]

    outputs = []
    tmp = []
    for item in output:
        if item == '':
            outputs.append(tmp)
            tmp = []
        else:
            tmp.append(item)

    status = []
    for output_l in outputs:
        output_l_int = map(int, output_l)
        if [idx for idx, step in enumerate(output_l_int) if step > 0]:
            status.append(1)
        elif [idx for idx, step in enumerate(output_l_int) if step < 0]:
            status.append(-1)
        else:
            status.append(0)

    return status

def check_docking(jobid, ligs_idxs, ntargets, submitted_on='pharma'):

    # the following path is supposed to exist on the remote machine
    remote_path = 'tmp/results'
    workdir = 'job_' + jobid

    remote_dir = remote_path + '/' + workdir

    scriptname = write_check_docking_script(remote_dir, ligs_idxs)

    output = subprocess.check_output("ssh pharma 'bash -s' < " + scriptname, shell=True)
    status = get_docking_status(output)

    return status_ligs
