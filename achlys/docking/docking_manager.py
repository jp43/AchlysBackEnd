from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_docking_script(checkjob):

    ncpus = checkjob.ntargets
    ressource = checkjob.docking_settings['ressource']

    with open('run_docking.sh', 'w') as file:
        script ="""#!/bin/bash
#SBATCH --time=10-00:00
#SBATCH --partition=serial
#SBATCH --job-name="docking"
#SBATCH --cpus-per-task=1
#SBATCH --array=1-%(ncpus)s

cd $SLURM_SUBMIT_DIR
source ~preto/.bash_profile

for isodir in iso*; do 
  # (A) prepare files for docking
  mkdir ${isodir}/target${SLURM_ARRAY_TASK_ID}
  cd ${isodir}/target${SLURM_ARRAY_TASK_ID}

  # (B) run docking
  rundock -r ../../../targets/target${SLURM_ARRAY_TASK_ID}.pdb -l ../ligand.mol2 -f ../../../config.ini
  echo $? > status.out
  cd ../..
done
"""% locals()
        file.write(script)

def submit_docking(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    nligs = checkjob.nligs
    ntargets = checkjob.ntargets
    ressource = checkjob.docking_settings['ressource']
     
    firstcommand = ssh.get_first_command(ressource)
    submitcommand = ssh.get_submit_command(ressource)
    path = ssh.get_remote_path(jobid, ressource)

    # create results directory on the remote machine
    status = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'if [ ! -d %s ]; then mkdir %s; echo 1; else echo 0; fi'"%(ressource, path, path)), \
        shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst == 1:
        write_docking_script(checkjob)

        # secure copy ligand files
        subprocess.check_output(ssh.coat_ssh_cmd("tar -cf - {config.ini,lig*/iso*,targets,run_docking.sh} | \
ssh -C %(ressource)s '(cd %(path)s; tar -xf -)'"%locals()), shell=True, executable='/bin/bash')
        os.remove('run_docking.sh')

    ligs_idxs_s = ' '.join(map(str,ligs_idxs))

    # prepare docking jobs
    scriptname = 'submit_docking.sh'
    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# submit jobs
for idx in %(ligs_idxs_s)s; do
  cd lig$((idx+1))
  %(submitcommand)s ../run_docking.sh # submit job
  cd ..
done"""% locals()
        file.write(script)

    subprocess.check_output(ssh.coat_ssh_cmd("ssh %s '%s bash -s' < %s"%(ressource,firstcommand,scriptname)), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def check_docking(checkjob, ligs_idxs):

    ntargets = checkjob.ntargets
    jobid = checkjob.jobid
    ressource = checkjob.docking_settings['ressource']
    firstcommand = ssh.get_first_command(ressource)

    path = ssh.get_remote_path(jobid, ressource)

    ligs_idxs_s = ' '.join(map(str, ligs_idxs))
    scriptname = 'check_docking.sh'

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# check the status of each docking job
for idx in %(ligs_idxs_s)s; do
  status=0
  for dir in lig$((idx+1))/iso*/target*; do
    filename=$dir/status.out
    if [[ -f $filename ]]; then
      num=`cat $filename`
      if [ $num -ne 0 ]; then # job ended with an error
        status=1
      fi
    elif [ $status -ne 1 ]; then # job is still running
      status=-1
    fi
  done
  echo $status
done"""% locals()
        file.write(script)

    output =  subprocess.check_output(ssh.coat_ssh_cmd("ssh %s '%s bash -s' < %s"%(ressource,firstcommand,scriptname)),\
        shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    return status
