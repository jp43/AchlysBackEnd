from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_docking_job_array(ncpus, queue='achlys.q,serial.q,parallel.q'):

    with open('run_docking.sge', 'w') as file:
        script ="""#$ -N docking
#$ -q %(queue)s
#$ -l h_rt=168:00:00
#$ -t 1-%(ncpus)s:1
#$ -cwd
#$ -S /bin/bash

source ~/.bash_profile

cd target$((SGE_TASK_ID-1))

python ../run_docking.py -f ../config.ini
echo $? > status.txt
"""% locals()
        file.write(script)

def submit_docking(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    nligs = checkjob.nligs
    ntargets = checkjob.ntargets
     
    path = ssh.get_remote_path(jobid, 'pharma')

    # create results directory on the remote machine (pharma)
    status = subprocess.check_output("ssh pharma 'if [ ! -d %s ]; then mkdir %s; echo 1; else echo 0; fi'"%(path, path), shell=True)
    isfirst = int(status)

    if isfirst == 1:
        write_docking_job_array(ntargets)
        achlysdir = os.path.realpath(__file__)
        py_docking_script  = '/'.join(achlysdir.split('/')[:-1]) + '/run_docking.py'

        # secure copy ligand files
        subprocess.call("scp lig*/lig*.pdb targets/* config.ini \
            run_docking.sge %s pharma:%s/."%(py_docking_script,path), shell=True)

        os.remove('run_docking.sge')

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    # Prepare docking jobs
    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  # prepare files for docking 
  mkdir lig$lig_id

  cp config.ini run_docking.sge run_docking.py lig$lig_id/
  for target_id in `seq 1 %(ntargets)s`; do
    mkdir lig$lig_id/target$((target_id-1))
    cp lig$lig_id.pdb lig$lig_id/target$((target_id-1))/lig.pdb
    cp target$((target_id-1)).pdb lig$lig_id/target$((target_id-1))/target.pdb
  done
done

# submit jobs
for lig_id in %(ligs_idxs_str)s; do
  cd lig$lig_id
  qsub run_docking.sge # submit job
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh pharma 'bash -s' < tmp.sh", shell=True)
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_docking_script(path, ligs_idxs, ntargets):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  # check status of each docking
  status=0
  cd lig$lig_id
  for target_id in `seq 1 %(ntargets)s`; do
    filename=target$((target_id-1))/status.txt 
    if [ -f $filename ]; then
      num=`cat $filename`
      if [ $num -ne 0 ]; then
        status=1
      fi
    else # the docking simulation is still running
      status=-1
    fi
  done 

  # if the docking is done, get the poses
  # with the best scoring functions
  if [ $status -eq 0 ]; then
    echo "import ConfigParser
import numpy as np

config = ConfigParser.SafeConfigParser()
config.read('config.ini')

if config.has_option('DOCKING', 'nposes'):
    nposes  = config.getint('DOCKING', 'nposes') 
else:
    nposes = 7

free_energy = np.zeros(%(ntargets)s)

for idx in range(%(ntargets)s):
    with open('target%%i/affinity.dat'%%idx, 'r') as fefile:
        line = fefile.next().replace('\\n','')
        free_energy[idx] = float(line)

idxs = np.argsort(free_energy)
idxs = idxs[:nposes]
print ' '.join(map(str,idxs.tolist()))" > get_affinity.py

    targets_idxs=`python get_affinity.py`

    pose_idx=0
    for idx in $targets_idxs; do
      mkdir pose$pose_idx
      mkdir pose$pose_idx/common
      cp target$idx/complex.pdb pose$pose_idx/common/
      cp target$idx/lig_out_h.pdb pose$pose_idx/common/lig.pdb
      cp target$idx/affinity.dat pose$pose_idx/
      cp target$idx/*.out pose$pose_idx/
      pose_idx=$((pose_idx+1))
    done

    # remove target files to free storage memory
    rm -rf target*
  fi

  echo $status
  cd ..
done"""% locals()
        file.write(script)

def check_docking(checkjob, ligs_idxs):

    ntargets = checkjob.ntargets
    jobid = checkjob.jobid

    path = ssh.get_remote_path(jobid, 'pharma')

    write_check_docking_script(path, ligs_idxs, ntargets)
    output = subprocess.check_output("ssh pharma 'bash -s' < tmp.sh", shell=True)
    status = ssh.get_status(output)

    return status
