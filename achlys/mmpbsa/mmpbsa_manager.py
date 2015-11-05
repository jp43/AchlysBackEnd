from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_mmpbsa_job_script(ligs_idxs, nposes, options):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    ressource = options['ressource']
    walltime = options['walltime']

    if ressource == 'pharma':
        scriptname = 'run_mmpbsa.sge'
        with open(scriptname, 'w') as file:
            script ="""#$ -N mmpbsa
#$ -q achlys.q,parallel.q
#$ -l h_rt=%(walltime)s
#$ -cwd
#$ -t 1-%(nposes)s:1
#$ -pe smp 2
#$ -S /bin/bash

export AMBERHOME=/pmshare/amber/amber12-20120918
export PATH=$AMBERHOME/bin:/opt/openmpi/1.6/gcc/bin:$PATH
export LD_LIBRARY_PATH=$AMBERHOME/lib64:/opt/openmpi/1.6/gcc/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/opt/mgltools/1.5.4/MGLToolsPckgs:$HOME/achlys/lib/python2.7/site-packages:$HOME/local/lib/python2.7/site-packages:$PYTHONPATH

lig_id=`echo $PWD | grep -o lig.* | sed -n s/lig//p`

mkdir pose$((SGE_TASK_ID-1))/mmpbsa
mv md${lig_id}.out/pose$((SGE_TASK_ID-1)).md.dcd pose$((SGE_TASK_ID-1))/mmpbsa/md.dcd

cd pose$((SGE_TASK_ID-1))/mmpbsa

python ../../../run_mmpbsa.py -f ../config.ini
echo $? > status.txt
"""% locals()
            file.write(script)
    elif ressource == 'grex':
        scriptname = 'run_mmpbsa.pbs'
        with open(scriptname, 'w') as file:
            script ="""#!/bin/bash 
#PBS -l walltime=%(walltime)s
#PBS -l mem=12gb
#PBS -l nodes=1:ppn=6
#PBS -q default
#PBS -N mmpbsa

cd $PBS_O_WORKDIR
lig_id=`echo $PWD | grep -o lig.* | sed -n s/lig//p`

for i in `seq 1 %(nposes)s`; do
    j=$((i-1))
    mkdir pose$j/mmpbsa

    mv md${lig_id}.out/pose$j.md.dcd pose$j/mmpbsa/md.dcd
    cd pose$j/mmpbsa

    python ../../../run_mmpbsa.py -f ../config.ini -n 6
    echo $? > status.txt
    cd ../../
done
"""% locals()
            file.write(script)

    return scriptname

def submit_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    nposes = checkjob.nposes
    mmpbsa_options = checkjob.mmpbsa_options
    ressource = mmpbsa_options['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    status = subprocess.check_output("ssh %s 'if [ ! -f %s/run_mmpbsa.py ]; then echo 1; else echo 0; fi'"%(ressource, path), shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst == 1:
        scriptname = write_mmpbsa_job_script(ligs_idxs, nposes, mmpbsa_options)
        achlysdir = os.path.realpath(__file__)
        py_docking_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_mmpbsa,analysis}.py'

        subprocess.call("scp %s %s %s:%s/."%(scriptname,py_docking_scripts,ressource,path), shell=True, executable='/bin/bash')
        os.remove(scriptname)

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    # Prepare mmpbsa
    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# submit jobs
for lig_id in %(ligs_idxs_str)s; do
  cd lig$lig_id
  qsub ../%(scriptname)s # submit job
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh %s 'bash -s' < tmp.sh"%ressource, shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_mmpbsa_script(path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('tmp.sh', 'w') as file:
        script ="""set -e
source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  # check status of each docking
  status=0
  cd lig$lig_id
  for posdir in pose*; do
    if [ -d $posdir ]; then
      filename=$posdir/mmpbsa/status.txt 
      if [ -f $filename ]; then
        num=`cat $filename`
        if [ $num -ne 0 ]; then
          status=1
        fi
      else # the mmpbsa simulation is still running
        status=-1
      fi
    fi
  done
  echo $status
  if [ $status -eq 0 ]; then
    python ../analysis.py -f config.ini
    mv lig.info lig${lig_id}.info
  fi
  cd ..
done"""% locals()
        file.write(script)

def check_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    mmpbsa_options = checkjob.mmpbsa_options
    ressource = mmpbsa_options['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    write_check_mmpbsa_script(path, ligs_idxs)
    output = subprocess.check_output("ssh %s 'bash -s' < tmp.sh"%ressource, shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    ligs_done_idxs = [ligs_idxs[idx] for idx in range(len(ligs_idxs)) if status[idx] == 'done']

    if ligs_done_idxs:
        if len(ligs_done_idxs) == 1:
            ligs_done_idxs_bash = str(ligs_done_idxs[0])
        else:
            ligs_done_idxs_bash = '{' + ','.join(map(str,ligs_done_idxs)) + '}'

        subprocess.call("scp %s:%s/lig%s/lig*.info ."%(ressource,path,ligs_done_idxs_bash), shell=True, executable='/bin/bash') 
        for idx in ligs_done_idxs:
            shutil.move('lig%s.info'%idx,'lig%s/lig.info'%idx)

    return status
