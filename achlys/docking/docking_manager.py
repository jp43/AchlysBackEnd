from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_docking_script(ncpus, queue='achlys.q,serial.q,parallel.q'):

    with open('run_docking.sge', 'w') as file:
        script ="""#$ -N docking-achlys
#$ -q %(queue)s
#$ -l h_rt=168:00:00
#$ -t 1-%(ncpus)s:1
#$ -cwd
#$ -S /bin/bash

source ~/.bash_profile

# (A) prepare files for docking
lig_id=`echo $PWD | grep -o lig.* | sed -n s/lig//p`

mkdir target$((SGE_TASK_ID-1))
cp ../lig$lig_id.pdb target$((SGE_TASK_ID-1))/lig.pdb
cp ../target$((SGE_TASK_ID-1)).pdb target$((SGE_TASK_ID-1))/target.pdb
echo $? > status1.out

# (B) run docking
cd target$((SGE_TASK_ID-1))

python ../../run_docking.py -f ../../config.ini
echo $? > status2.out
"""% locals()
        file.write(script)

def submit_docking(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    nligs = checkjob.nligs
    ntargets = checkjob.ntargets
    ressource = checkjob.docking_settings['ressource']
     
    path = ssh.get_remote_path(jobid, ressource)

    # create results directory on the remote machine
    status = subprocess.check_output("ssh %s 'if [ ! -d %s ]; then mkdir %s; echo 1; else echo 0; fi'"%(ressource, path, path), shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst == 1:
        write_docking_script(ntargets)
        achlysdir = os.path.realpath(__file__)
        py_docking_script  = '/'.join(achlysdir.split('/')[:-1]) + '/run_docking.py'

        # secure copy ligand files
        subprocess.call("scp lig*/lig*.pdb targets/* config.ini \
            run_docking.sge %s %s:%s/."%(py_docking_script,ressource,path), shell=True, executable='/bin/bash')
        os.remove('run_docking.sge')

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    # prepare docking jobs
    scriptname = 'submit_docking.sh'
    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# submit jobs
for lig_id in %(ligs_idxs_str)s; do
  mkdir lig$lig_id
  cd lig$lig_id
  qsub ../run_docking.sge # submit job
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh %s 'bash -s' < %s"%(ressource,scriptname), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def check_docking(checkjob, ligs_idxs):

    ntargets = checkjob.ntargets
    jobid = checkjob.jobid
    ressource = checkjob.docking_settings['ressource']

    path = ssh.get_remote_path(jobid, ressource)

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    scriptname = 'check_docking.sh'

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# check the status of each docking job
for lig_id in %(ligs_idxs_str)s; do
  status=0
  for target_id in `seq 1 %(ntargets)s`; do
    filename=lig${lig_id}/target$((target_id-1))/status2.out 
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

    output = subprocess.check_output("ssh pharma 'bash -s' < %s"%scriptname, shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    return status
