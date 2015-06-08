import os
import uuid
import tempfile
import subprocess

def run_script(script, remote_host, files_to_copy=None, output=None):

    if output is None:
        output = remote_host + '.out'

    # make temporary directory where the script will be run
    tmpdir = '.' + str(uuid.uuid4()).split('-')[0]
    subprocess.check_call("ssh " + remote_host + " 'mkdir %s'"%tmpdir, shell=True)

    if files_to_copy:
        subprocess.check_call("scp -r " + (' ').join(files_to_copy) + " " + remote_host + ":" + tmpdir, shell=True)
    fh, tmp = tempfile.mkstemp(suffix='.sh')

    heading = """source ~/.bash_profile
# go to tmp directory
cd %(tmpdir)s"""% locals()

    ending = """cd $HOME
rm -rf %(tmpdir)s"""% locals()

    script = heading + '\n' + script + '\n' + ending

    with open(tmp, 'w') as file:
        file.write(script)

    subprocess.check_call("ssh " + remote_host + " 'bash -s' < " + tmp + " > " + output, shell=True)
