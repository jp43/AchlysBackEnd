from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_mmpbsa_job_script(ligs_idxs, queue='achlys.q,parallel.q'):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('run_mmpbsa.sge', 'w') as file:
        script ="""#$ -N mmpbsa
#$ -q achlys.q,parallel.q
#$ -l h_rt=168:00:00
#$ -cwd
#$ -t 1-7:1
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
cd ..

# get number of frames in trajectory file
echo "parm common/start.prmtop
trajin mmpbsa/md.dcd 1 1 1
strip :WAT
strip :Na+
strip :Cl-
trajout md.pdb pdb" > cpptraj.in

cpptraj -i cpptraj.in > cpptraj.out

echo "f = open('cpptraj.out', 'r')
for line in f:
    if all([word in line for word in ['contains','frames']]):
        print line.split()[2]" > nframes.py

nframes=`python nframes.py`
rm -rf nframes.py md.pdb cpptraj.in cpptraj.out

echo " parm common/start.prmtop
trajin mmpbsa/md.dcd $nframes $nframes 1
strip :WAT
strip :Na+
strip :Cl-
trajout end-md.pdb pdb" > cpptraj.in

cpptraj -i cpptraj.in > cpptraj.out
rm -rf cpptraj.in cpptraj.out
"""% locals()
        file.write(script)

def submit_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'pharma')

    # create results directory on the remote machine (pharma)
    status = subprocess.check_output("ssh pharma 'if [ ! -f %s/run_mmpbsa.py ]; then echo 1; else echo 0; fi'"%path, shell=True)
    isfirst = int(status)

    if isfirst == 1:
        write_mmpbsa_job_script(ligs_idxs)#, queue='ibmblade.q')
        achlysdir = os.path.realpath(__file__)
        py_docking_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_mmpbsa,analysis}.py'

        subprocess.call("scp run_mmpbsa.sge %s pharma:%s/."%(py_docking_scripts,path), shell=True)
        os.remove('run_mmpbsa.sge')

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    # Prepare mmpbsa
    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# submit jobs
for lig_id in %(ligs_idxs_str)s; do
  cd lig$lig_id
  qsub ../run_mmpbsa.sge # submit job
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh pharma 'bash -s' < tmp.sh", shell=True)
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
    path = ssh.get_remote_path(jobid, 'pharma')

    write_check_mmpbsa_script(path, ligs_idxs)
    output = subprocess.check_output("ssh pharma 'bash -s' < tmp.sh", shell=True)
    status = ssh.get_status(output)

    ligs_done_idxs = [ligs_idxs[idx] for idx in range(len(ligs_idxs)) if status[idx] == 'done']

    if ligs_done_idxs:
        if len(ligs_done_idxs) == 1:
            ligs_done_idxs_bash = str(ligs_done_idxs[0])
        else:
            ligs_done_idxs_bash = '{' + ','.join(map(str,ligs_done_idxs)) + '}'

        subprocess.call("scp pharma:%s/lig%s/lig*.info ."%(path,ligs_done_idxs_bash), shell=True) 
        for idx in ligs_done_idxs:
            shutil.move('lig%s.info'%idx,'lig%s/lig.info'%idx)

    return status
