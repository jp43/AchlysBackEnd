from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_startup_job_script(ntargets, nposes, queue='achlys.q,serial.q,parallel.q'):

    with open('run_startup.sge', 'w') as file:
        script ="""#$ -N startup-achlys
#$ -q %(queue)s
#$ -l h_rt=168:00:00
#$ -cwd
#$ -S /bin/bash

source ~/.bash_profile

# (A) prepare files for md startup
echo "import ConfigParser
import numpy as np

nposes = %(nposes)s
free_energy = np.zeros(%(ntargets)s)

for idx in range(%(ntargets)s):
    with open('target%%i/affinity.dat'%%idx, 'r') as fefile:
        line = fefile.next().replace('\\n','')
        free_energy[idx] = float(line)

idxs = np.argsort(free_energy)
idxs = idxs[:nposes]
print ' '.join(map(str,idxs.tolist()))" > get_targets_idxs.py

targets_idxs=`python get_targets_idxs.py`
echo $targets_idxs > targets_idxs.dat

pose_idx=0
for idx in $targets_idxs; do
  mkdir pose$pose_idx
  mkdir pose$pose_idx/common

  cp target$idx/complex.pdb pose$pose_idx/common/
  cp target$idx/lig_out_h.pdb pose$pose_idx/common/lig.pdb
  cp target$idx/affinity.dat pose$pose_idx/
  pose_idx=$((pose_idx+1))
done

# (B) run md startup
for posdir in pose*; do 
  cd $posdir/
  python ../../run_md.py startup --withlig -f ../../config.ini
  echo $? > status2.out
  cd ..
done
"""% locals()
        file.write(script)

def submit_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    nposes = checkjob.nposes
    ntargets = checkjob.ntargets
    ressource = checkjob.startup_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    # create results directory on the remote machine (pharma)
    status = subprocess.check_output("ssh %s 'if [ ! -f %s/run_md.py ]; then echo 1; else echo 0; fi'"%(ressource,path), shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst == 1:
        write_startup_job_script(ntargets, nposes)
        achlysdir = os.path.realpath(__file__)
        py_md_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_md.py,NAMD.py,amber.py}'

        subprocess.call("scp config.ini run_startup.sge %s %s:%s/."%(py_md_scripts,ressource,path), shell=True, executable='/bin/bash')
        os.remove('run_startup.sge')

    # prepare md startup jobs
    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    scriptname = 'submit_startup.sh'
    with open(scriptname, 'w') as file:
        script ="""#!/bin/bash 
source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  cd lig$lig_id/
  qsub ../run_startup.sge # submit job
  cd ..
done"""% locals()
        file.write(script)

    # submit jobs
    subprocess.call("ssh %s 'bash -s' < %s"%(ressource,scriptname), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_startup_script(scriptname, path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# check the status of each startup job
for lig_id in %(ligs_idxs_str)s; do
  status=0
  for posdir in lig${lig_id}/pose*; do
    filename=$posdir/status2.out
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

def check_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    ressource = checkjob.startup_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    scriptname = 'check_startup.sh'
    write_check_startup_script(scriptname, path, ligs_idxs)

    output = subprocess.check_output("ssh %s 'bash -s' < %s"%(ressource,scriptname), shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    return status

def write_md_job_script(checkjob):

    jobid = checkjob.jobid
    ressource_startup = checkjob.startup_settings['ressource']
    path_startup = ssh.get_remote_path(jobid, ressource_startup)

    ressource = checkjob.md_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    with open('run_md.sh', 'w') as file:
        script ="""#!/bin/sh
# @ job_name           = md-achlys
# @ job_type           = bluegene
# @ error              = $(job_name).$(Host).$(jobid).err
# @ output             = $(job_name).$(Host).$(jobid).out
# @ bg_size            = 64
# @ wall_clock_limit   = 24:00:00
# @ bg_connectivity    = Torus
# @ queue 

# (A) prepare files for md
cd $PWD
lig_id=`echo $PWD | grep -o lig.* | sed -n s/lig//p`
ssh -C %(ressource_startup)s "cd %(path_startup)s; tar -cf - lig${lig_id}/pose* --exclude=\\"status1.out\\" --exclude=\\"status2.out\\"" | `cd ..; tar -xf -`
echo $? > status1.out

# (B) run files for md
for posdir in pose*; do 
  cd $posdir
  python ../../run_md.py min equil md -f ../../config.ini --ncpus 1024 --bgq --withlig
  echo $? > status2.out
  cd ..
done"""% locals()
        file.write(script)

def submit_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    ressource = checkjob.md_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    status = subprocess.check_output("ssh %s 'if [ ! -d %s ]; then mkdir %s; echo 1; else echo 0; fi'"%(ressource,path,path), shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst:
        write_md_job_script(checkjob)
        achlysdir = os.path.realpath(__file__)
        py_md_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_md.py,NAMD.py,amber.py}'
        subprocess.call("scp config.ini run_md.sh %s %s:%s/."%(py_md_scripts,ressource,path), shell=True, executable='/bin/bash')

    # prepare md jobs
    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    scriptname = 'submit_md.sh'
    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  mkdir lig$lig_id
  cd lig$lig_id/
  llsubmit ../run_md.sh
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh %s 'bash -s' < %s"%(ressource,scriptname), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]
    return status

def write_check_md_script(scriptname, path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# check the status of each md job
for lig_id in %(ligs_idxs_str)s; do
  status=0
  for posdir in pose*; do
    filename=lig${lig_id}/$posdir/status2.out
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

def check_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    ressource = checkjob.md_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    scriptname = 'check_md.sh'
    write_check_startup_script(scriptname, path, ligs_idxs)

    output = subprocess.check_output("ssh %s 'bash -s' < %s"%(ressource,scriptname), shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    return status
