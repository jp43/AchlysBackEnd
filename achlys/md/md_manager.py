from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_startup_job_script(queue='achlys.q,serial.q,parallel.q'):

    with open('run_startup.sge', 'w') as file:
        script ="""#$ -N md_startup
#$ -q %(queue)s
#$ -l h_rt=168:00:00
#$ -cwd
#$ -S /bin/bash

source ~/.bash_profile

for posdir in pose*; do 
  cd $posdir/
  python run_md.py startup --withlig -f config.ini
  echo $? > status.txt
  cd ..
done
"""% locals()
        file.write(script)

def submit_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'pharma')

    # create results directory on the remote machine (pharma)
    status = subprocess.check_output("ssh pharma 'if [ ! -f %s/run_md.py ]; then echo 1; else echo 0; fi'"%path, shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst == 1:
        write_startup_job_script()
        achlysdir = os.path.realpath(__file__)
        py_docking_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_md.py,NAMD.py,amber.py}'
        py_docking_scripts += ' ' + '/'.join(achlysdir.split('/')[:-2]) + '/tools/ssh.py'

        #print "scp run_startup.sge %s pharma:%s/."%(py_docking_scripts,path)
        subprocess.call("scp run_startup.sge %s pharma:%s/."%(py_docking_scripts,path), shell=True, executable='/bin/bash')
        os.remove('run_startup.sge')

    # submit startup scripts
    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    with open('tmp.sh', 'w') as file:
        script ="""#!/bin/bash 
source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
    cd lig$lig_id/
    for posdir in pose*; do
      cp ../config.ini ../run_md.py ../amber.py ../NAMD.py ../ssh.py $posdir/
    done
    qsub ../run_startup.sge
    cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh pharma 'bash -s' < tmp.sh", shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_startup_script(path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  status=0
  cd lig$lig_id
  for posdir in pose*; do
    filename=$posdir/status.txt 
    if [ -d $posdir ]; then
      if [ -f $filename ]; then
        num=`cat $filename`
        if [ $num -ne 0 ]; then
          status=1
        fi
      else # the startup simulation is still running
        status=-1
      fi
    fi
  done
  echo $status
  cd ..
done"""% locals()
        file.write(script)

def check_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'pharma')

    write_check_startup_script(path, ligs_idxs)
    output = subprocess.check_output("ssh pharma 'bash -s' < tmp.sh", shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    return status

def write_md_job_script():

    with open('run_md.sh', 'w') as file:
        script ="""#!/bin/sh
# @ job_name           = md
# @ job_type           = bluegene
# @ error              = $(job_name).$(Host).$(jobid).err
# @ output             = $(job_name).$(Host).$(jobid).out
# @ bg_size            = 64
# @ wall_clock_limit   = 24:00:00
# @ bg_connectivity    = Torus
# @ queue 

cd $PWD
#tar -xf poses*.tar.gz
#rm -rf poses*.tar.gz
for posdir in pose*; do 
  cd $posdir
  python run_md.py min equil md -f config.ini --ncpus 1024 --bgq --withlig
  echo $? > status.txt
  cd ..
done"""% locals()
        file.write(script)

def write_check_startup_transfer_script(path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  # check status of each docking
  status=0
  filename=lig${lig_id}/poses${lig_id}.tar.gz
  if [ -f $filename ]; then
    status=0
  else
    status=-1
  fi
  echo $status
  cd ..
done"""% locals()
        file.write(script)

def submit_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    path = ssh.get_remote_path(jobid, 'bgq')
    path_pharma = ssh.get_remote_path(jobid, 'pharma') 

    status = subprocess.check_output("ssh bgq 'if [ ! -d %s ]; then mkdir %s; echo 1; else echo 0; fi'"%(path,path), shell=True, executable='/bin/bash')
    isfirst = int(status)

    if len(ligs_idxs) == 1:
        ligs_idxs_bash = str(ligs_idxs[0])
    else:
        ligs_idxs_bash = '{' + ','.join(map(str,ligs_idxs)) + '}'

    if isfirst:
        write_md_job_script()
        subprocess.call("scp run_md.sh bgq:%s/."%path, shell=True, executable='/bin/bash')

    subprocess.check_call("ssh -C pharma 'cd %s; tar -cf - lig%s/pose* --exclude=""status.txt""' | ssh -C bgq 'cd %s/. && tar -xf -'"%(path_pharma, ligs_idxs_bash, path), shell=True, executable='/bin/bash')

    # submit startup scripts
    ligs_idxs_str = ' '.join(map(str, ligs_idxs))
    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  cd lig$lig_id/
  llsubmit ../run_md.sh
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call("ssh bgq 'bash -s' < tmp.sh", shell=True, executable='/bin/bash')
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
    if [ ! -d md${lig_id}.out ]; then
      mkdir md${lig_id}.out
      for posdir in pose*; do
        mv $posdir/md.dcd md${lig_id}.out/$posdir.md.dcd
      done
      touch md${lig_id}.out/.pose.md.dcd # create an empty file
    fi
  fi
  cd ..
done"""% locals()
        file.write(script)

def write_check_md_transfer_script(path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open('tmp.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  # check status of each docking
  status=0
  if [ -f lig${lig_id}/md${lig_id}.out/.pose.md.dcd ]; then
    status=0 
  else
    status=-1
  fi
  echo $status
  cd ..
done"""% locals()
        file.write(script)

def check_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid

    ressource1 = 'bgq'
    path1 = ssh.get_remote_path(jobid, ressource1)
    mmpbsa_options = checkjob.mmpbsa_options
    ressource2 = mmpbsa_options['ressource']
    path2 = ssh.get_remote_path(jobid, ressource2)

    write_check_md_script(path1, ligs_idxs)
    output = subprocess.check_output("ssh %s 'bash -s' < tmp.sh"%ressource1, shell=True, executable='/bin/bash')
    status = ssh.get_status(output)
    status_lig = status

    ligs_done_idxs = [ligs_idxs[idx] for idx in range(len(ligs_idxs)) if status[idx] == 'done']

    # create results directory on the remote machine
    subprocess.call("ssh %s 'if [ ! -d %s ]; then mkdir %s; fi'"%(ressource2,path2,path2), shell=True, executable='/bin/bash')

    # check how many ligands have done transfering their files
    write_check_md_transfer_script(path2, ligs_done_idxs)
    output_transfer = subprocess.check_output("ssh %s 'bash -s' < tmp.sh"%ressource2, shell=True, executable='/bin/bash')
    status_transfer = ssh.get_status_transfer(output_transfer)
    ligs_not_transfered_idxs = [ligs_done_idxs[idx] for idx in range(len(ligs_done_idxs)) if status_transfer[idx] == 'waiting']

    if ligs_not_transfered_idxs:
        if len(ligs_not_transfered_idxs) == 1:
            ligs_not_transfered_idxs_bash = str(ligs_not_transfered_idxs[0])
        else:
            ligs_not_transfered_idxs_bash = '{' + ','.join(map(str,ligs_not_transfered_idxs)) + '}'

        # check if folders "common" do not exist on the remote machine (grex)
        status_common = subprocess.check_output("ssh %s 'if [ ! -d %s/lig%s/pose0 ]; then echo 1; else echo 0; fi'"%(ressource2,path2,ligs_not_transfered_idxs[0]), shell=True, executable='/bin/bash')
        if int(status_common) == 1:
            files_to_transfer = 'lig%s/{pose*/{common,config.ini},md*.out}'%ligs_not_transfered_idxs_bash
        else:
            files_to_transfer = 'lig%s/pose*/common'%ligs_not_transfered_idxs_bash

        subprocess.call("ssh -C %s 'cd %s; tar -cf - %s' | ssh -C %s 'cd %s; tar -xf -'"%(ressource1,path1,files_to_transfer,ressource2,path2), shell=True, executable='/bin/bash')
    return status
