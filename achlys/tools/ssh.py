import os
import uuid
import tempfile
import subprocess

def run_script(script, remote_host, files_to_copy=None, output=None, purge=True, directory=None):

    if output is None:
        output = remote_host + '.out'

    if directory is None:
        # make temporary directory where the script will be run
        tmpdir = '.' + str(uuid.uuid4()).split('-')[0]
        subprocess.check_call("ssh " + remote_host + " 'mkdir %s'"%tmpdir, shell=True)
    else:
        tmpdir = directory

    if files_to_copy:
        subprocess.check_call("scp -r " + (' ').join(files_to_copy) + " " + remote_host + ":" + tmpdir, shell=True)

    heading = """source ~/.bash_profile
# go to working directory
cd %(tmpdir)s"""% locals()

    if purge:
        ending = """cd $HOME
rm -rf %(tmpdir)s"""% locals()
    else:
        ending = ""

    script = heading + '\n' + script + '\n' + ending

    with open('tmp.sh', 'w') as file:
        file.write(script)

    subprocess.check_call("ssh " + remote_host + " 'bash -s' < tmp.sh > " + output, shell=True)


def get_first_command(machine):

    if machine ==  'hermes':
        cmd = 'source /etc/profile;'
    else:
        cmd = ''

    return cmd

def get_remote_path(jobid, machine):
    """ get path on the remote machine"""

    if machine == 'bgq':
        prefix = 'scratch/results'
    elif machine == 'pharma':
        # the following path is supposed to exist
        prefix = 'scratch/achlys'
    elif machine == 'grex':
        prefix = 'scratch/achlys' 
    elif machine ==  'hermes':
        prefix = 'scratch/achlys'

    suffix = 'job_' + jobid
    path = prefix + '/' + suffix
    return path

def get_status(output):

    status = []
    for num in map(int,output.split('\n')[:-1]):
        if num == 0:
            status.append('done')
        elif num == -1:
            status.append('running')
        else:
            status.append('error')

    return status

def get_status_transfer(output):

    status = []
    for num in map(int,output.split('\n')[:-1]):
        if num == 0:
            status.append('done')
        elif num == -1:
            status.append('waiting')

    return status
