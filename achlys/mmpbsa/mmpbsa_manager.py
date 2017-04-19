from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_mmpbsa_job_script(checkjob):

    jobid = checkjob.jobid
    nposes = checkjob.nposes

    ressource_md = checkjob.md_settings['ressource']
    path_md = ssh.get_remote_path(jobid, ressource_md)

    mmpbsa_settings = checkjob.mmpbsa_settings
    ressource = mmpbsa_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    ssh_cmd = ssh.coat_ssh_cmd("""ssh -C %(ressource_md)s \"cd %(path_md)s/lig${lig_id}/pose${pose_id}/ligand; tar -cf - md.dcd\" | tar -xf -"""% locals())

    with open('run_mmpbsa.sh', 'w') as file:
        script ="""#!/bin/bash
#SBATCH --time=168-00:00
#SBATCH --partition=largemem
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4

lig_id=`echo $PWD | grep -o 'lig.*' | sed -n s/lig//p | cut -d/ -f1`
pose_id=`echo $PWD | grep -o 'pose.*' | sed -n s/pose//p`

# (A) prepare files for mmpbsa
cd ligand
%(ssh_cmd)s

mkdir mmpbsa
cd mmpbsa

# (B) run mmpbsa
run_mmpbsa.py -nt 4 -s ':WAT,Cl-,Na+' -n ':LIG'
echo $? > status.out
"""% locals()
        file.write(script)

def submit_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    nposes = checkjob.nposes
    mmpbsa_settings = checkjob.mmpbsa_settings
    ressource = mmpbsa_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    # create job folder if does not exist
    status = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'if [ ! -f %s/run_mmpbsa.sh ]; then if [ ! -d %s ]; then mkdir %s; fi; echo 1; else echo 0; fi'"\
                 %(ressource, path, path, path)), shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst == 1:
        write_mmpbsa_job_script(checkjob)
        achlysdir = os.path.realpath(__file__)
        analysis_script = '/'.join(achlysdir.split('/')[:-1]) + '/../tools/analysis.py'
        subprocess.call(ssh.coat_ssh_cmd("scp config.ini run_mmpbsa.sh %s %s:%s/."%(analysis_script,ressource,path)), shell=True, executable='/bin/bash')
        os.remove('run_mmpbsa.sh')

    ligs_idxs_s = ' '.join(map(str, ligs_idxs))

    # Prepare mmpbsa
    with open('submit_mmpbsa.sh', 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# submit jobs
for idx in %(ligs_idxs_s)s; do
  ligdir=lig$((idx+1))
  if [[ ! -d $ligdir ]]; then
    mkdir $ligdir
  fi
  for posedir in $ligdir/pose{1..%(nposes)s}; do
    cd $posedir
    sbatch ../../run_mmpbsa.sh # submit job
    cd ../..
  done
done"""% locals()
        file.write(script)

    subprocess.call(ssh.coat_ssh_cmd("ssh %s 'bash -s' < submit_mmpbsa.sh"%ressource), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_mmpbsa_script(scriptname, path, ligs_idxs, nposes):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for idx in %(ligs_idxs_str)s; do
  # check status of each docking
  ligdir=lig$((idx+1)) 
  status=0
  for posdir in lig${lig_id}/pose{1..%(nposes)s}; do
    if [ -d $posdir ]; then
      filename=${posdir}/mmpbsa/status.out 
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
    cd $ligdir
    python ../analysis.py
    cd ..
  fi
done"""% locals()
        file.write(script)

def check_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    mmpbsa_settings = checkjob.mmpbsa_settings
    ressource = mmpbsa_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    scriptname = 'check_mmpbsa.sh'
    write_check_mmpbsa_script(scriptname, path, ligs_idxs, checkjob.nposes)
    output = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'bash -s' < %s"%(ressource,scriptname)), shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    ligs_done_idxs = [ligs_idxs[idx]+1 for idx in range(len(ligs_idxs)) if status[idx] == 'done']

    if ligs_done_idxs:
        if len(ligs_done_idxs) == 1:
            ligs_done_idxs_bash = str(ligs_done_idxs[0])
        else:
            ligs_done_idxs_bash = '{' + ','.join(map(str,ligs_done_idxs)) + '}'

        subprocess.call(ssh.coat_ssh_cmd("ssh -C %s \"cd %s; tar -cf - lig%s/{pbsa,gbsa}\" | `cd ../job_%s; tar -xf -` "%(ressource,path,ligs_done_idxs_bash,jobid)), shell=True, executable='/bin/bash')

    return status
