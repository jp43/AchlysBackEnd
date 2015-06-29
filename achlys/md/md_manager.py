from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_startup_job_script(ligs_idxs, queue='achlys.q'):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('run_startup.sge', 'w') as file:
        script ="""#$ -N md_startup
#$ -q %(queue)s
#$ -l h_rt=168:00:00
#$ -V
#$ -cwd
#$ -S /bin/bash

# run all the startup simulations in a row if possible
for lig_id in %(ligs_idxs_str)s; do
  cd lig$lig_id/
  for posdir in pose*; do 
    cd $posdir/
    python run_md.py startup --withlig -f config.ini
    echo $? > status.txt
    cd ..
  done
  cd ..
done"""% locals()
        file.write(script)

def submit_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'pharma')

    # create results directory on the remote machine (pharma)
    status = subprocess.check_output("ssh pharma 'if [ ! -f %s/run_md.py ]; then echo 1; else echo 0; fi'"%path, shell=True)
    isfirst = int(status)

    if isfirst == 1:
        write_startup_job_script(ligs_idxs, queue='achlys.q')
        achlysdir = os.path.realpath(__file__)
        py_docking_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_md.py,NAMD.py,amber.py}'
        py_docking_scripts += ' ' + '/'.join(achlysdir.split('/')[:-2]) + '/tools/ssh.py'

        subprocess.call("scp run_startup.sge %s pharma:%s/."%(py_docking_scripts,path), shell=True)
        os.remove('run_startup.sge')

    # submit startup scripts
    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
    for posdir in lig${lig_id}/pose*; do
      cp config.ini run_md.py amber.py NAMD.py ssh.py $posdir/
    done
done
qsub run_startup.sge"""% locals()
        file.write(script)

    subprocess.call("ssh pharma 'bash -s' < tmp.sh", shell=True)
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_startup_script(path, ligs_idxs):

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

def check_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'pharma')

    write_check_startup_script(path, ligs_idxs)
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

def write_md_job_script(ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('run_md.sh', 'w') as file:
        script ="""#!/bin/sh
# @ job_name           = md
# @ job_type           = bluegene
# @ error              = $(job_name).$(Host).$(jobid).err
# @ output             = $(job_name).$(Host).$(jobid).out
# @ bg_size            = 64
# @ wall_clock_limit   = 1:40:00
# @ bg_connectivity    = Torus
# @ queue 

python run_md.py min equil md -f config.ini --ncpus 1024 --bgq --withlig
echo $? > status.txt"""% locals()
        file.write(script)

def submit_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'bgq')

    status = subprocess.check_output("ssh bgq 'if [ ! -d %s ]; then mkdir %s; echo 1; else echo 0; fi'"%(path,path), shell=True)
    isfirst = int(status)

    if len(ligs_idxs) == 1:
        ligs_idxs_bash = str(ligs_idxs[0])
    else:
        ligs_idxs_bash = '{' + ','.join(ligs_idxs) + '}'    
    tarfiles = 'lig' + ligs_idxs_bash + '/poses*.tar.gz'

    if isfirst:
        write_md_job_script(ligs_idxs)

        achlysdir = os.path.realpath(__file__)
        py_docking_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_md.py,NAMD.py,amber.py}'
        py_docking_scripts += ' ' + '/'.join(achlysdir.split('/')[:-2]) + '/tools/ssh.py'

        subprocess.call("scp config.ini run_md.sh %s %s bgq:%s/."%(py_docking_scripts, tarfiles, path), shell=True)
        os.remove('run_md.sh')
    else:
        subprocess.call("scp %s bgq:%s/."%(tarfiles, path), shell=True)

    # submit startup scripts
    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  mkdir lig$lig_id/
  mv poses${lig_id}.tar.gz lig$lig_id/
  cd lig$lig_id/
  tar -xf poses${lig_id}.tar.gz
  rm -rf poses${lig_id}.tar.gz
  for posdir in pose*; do 
    cp ../{config.ini,run_md.sh,run_md.py,amber.py,NAMD.py,ssh.py} $posdir/
    cd $posdir
    llsubmit run_md.sh
    cd ..
  done
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh bgq 'bash -s' < tmp.sh", shell=True)
    status = ['running' for idx in range(len(ligs_idxs))]
    return status

def write_check_md_script(path, ligs_idxs):

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
    mkdir md${lig_id}.out
    for posdir in pose*; do
      cp $posdir/md.dcd md${lig_id}.out/$posdir.md.dcd
    done
  fi
  cd ..
done"""% locals()
        file.write(script)

def check_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path_bgq = ssh.get_remote_path(jobid, 'bgq')
    path_pharma = ssh.get_remote_path(jobid, 'pharma')

    write_check_md_script(path_bgq, ligs_idxs)
    output = subprocess.check_output("ssh bgq 'bash -s' < tmp.sh", shell=True)
    status = ssh.get_status(output)

    ligs_done_idxs = [ligs_idxs[idx] for idx in range(len(ligs_idxs)) if status[idx] == 'done']

    if ligs_done_idxs:
        if len(ligs_done_idxs) == 1:
            ligs_done_idxs_bash = str(ligs_done_idxs[0])
        else:
            ligs_done_idxs_bash = '{' + ','.join(ligs_done_idxs) + '}'

        subprocess.call("scp -r bgq:%s/lig%s/md*.out pharma:%s/"%(path_bgq,ligs_done_idxs_bash,path_pharma), shell=True)
    return status
