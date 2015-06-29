from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_mmpbsa_job_script(ligs_idxs, queue='ibmblade.q'):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('run_mmpbsa.sge', 'w') as file:
        script ="""#$ -N mmpbsa
#$ -q %(queue)s
#$ -l h_rt=168:00:00
#$ -V
#$ -t 1-7:1
#$ -pe openmpi 16
#$ -cwd
#$ -S /bin/bash
set -e

cd pose$((SGE_TASK_ID-1))/mmpbsa

python ../../run_mmpbsa.py -f ../config.ini
echo $? > status.txt
"""% locals()
        file.write(script)

def submit_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'pharma')

    # create results directory on the remote machine (pharma)
    status = subprocess.check_output("ssh pharma 'if [ ! -f %s/run_mmpbsa.py ]; then echo 1; else echo 0; fi'"%path, shell=True)
    isfirst = int(status)

    if isfirst == 1:
        write_mmpbsa_job_script(ligs_idxs, queue='ibmblade.q')
        achlysdir = os.path.realpath(__file__)
        py_docking_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/run_mmpbsa.py'

        subprocess.call("scp run_mmpbsa.sge %s pharma:%s/."%(py_docking_scripts,path), shell=True)
        os.remove('run_mmpbsa.sge')

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    # Prepare docking jobs
    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  cp run_mmpbsa.sge run_mmpbsa.py lig$lig_id/
  nposes=`ls -1 md$lig_id.out/ | wc -l`
  for posidx in `seq 0 $((nposes-1))`; do
    mkdir lig$lig_id/pose${posidx}/mmpbsa
    cp md${lig_id}.out/pose${posidx}.md.dcd lig$lig_id/pose${posidx}/mmpbsa/md.dcd
  done
done

# submit jobs
for lig_id in %(ligs_idxs_str)s; do
  cd lig$lig_id
  qsub run_mmpbsa.sge # submit job
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh pharma 'bash -s' < tmp.sh", shell=True)
    status = ['running' for idx in range(len(ligs_idxs))]

    sys.exit()
    return status

def write_check_mmpbsa_script(path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  # check status of each docking
  status=0
  cd lig$lig_id
  for posdir in pose*; do
    filename=$posdir/status.txt 
    if [ -f $filename ]; then
      num=`cat $filename`
      if [ $num -ne 0 ]; then
        status=1
      fi
    else # the startup simulation is still running
      status=-1
    fi
  done
  echo $status
  if [ $status -eq 0 ]; then
    rm -rf pose*/status.txt
    tar -zcf poses$lig_id.tar.gz pose*
  fi
  cd ..
done"""% locals()
        file.write(script)

def check_mmpbsa(checkjob, ligs_idxs):

    sys.exit()
    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'pharma')

    write_check_mmpbsa_script(path, ligs_idxs)
    output = subprocess.check_output("ssh pharma 'bash -s' < tmp.sh", shell=True)
    status = ssh.get_status(output)

    ligs_done_idxs = [ligs_idxs[idx] for idx in range(len(ligs_idxs)) if status[idx] == 'done']

    if ligs_done_idxs:
        if len(ligs_done_idxs) == 1:
            ligs_done_idxs_bash = str(ligs_done_idxs[0])
        else:
            ligs_done_idxs_bash = '{' + ','.join(ligs_done_idxs) + '}'

        subprocess.call("scp pharma:%s/lig%s/poses* ."%(path,ligs_done_idxs_bash), shell=True) 
        for idx in ligs_done_idxs:
            shutil.move('poses%s.tar.gz'%idx,'lig%s/'%idx)

    return status
