import sys
import os
import stat
import shutil
import ConfigParser
import time
import glob
import shutil
import subprocess

from MOBPred.amber import minimz
from MOBPred.tools import mol2

def prepare_compounds(input_files_l, jobID,  use_ligprep=True):

    # save current directory
    curdir = os.getcwd()

    for idx, file_l in enumerate(input_files_l):
        # create lig directory
        ligdir = 'lig' + str(idx+1)
        ligdir = 'job_%s/'%jobID + ligdir

        if not os.path.exists(file_l):
            raise ValueError("File %s not found!"%(file_l))
        file_l_abspath = os.path.abspath(file_l)
        basename, ext = os.path.splitext(file_l)
        os.mkdir(ligdir) # create directory

        # get compound original name
        with open(file_l) as ff:
           if ext == '.sdf':
               ligname = ff.next().strip()
           elif ext == '.smi':
               ligname = ff.next().split()[-1]

        ligprep_dir = ligdir +'/ligprep'
        os.mkdir(ligprep_dir)
        os.chdir(ligprep_dir)

        files_l_mol2 = generate_3D_structure(file_l_abspath)
        os.chdir(curdir)

        # create directory for each isomer
        for jdx, file_l_mol2 in enumerate(files_l_mol2):
            isodir = ligdir+'/iso%i'%(jdx+1)
            os.mkdir(isodir)
            shutil.copyfile(file_l_mol2, isodir+'/ligand.mol2')

        with open(ligdir+'/ligand.info', 'w') as infof:
            infof.write("Ligand orginal name: %s \n"%ligname)
            infof.write("Original file: %s\n"%file_l)

        with open(ligdir+'/step.out', 'w') as f:
            f.write("start step 1 (docking)")

def generate_3D_structure(file_l, flags="-ph 7.0 -pht 2.0 -i 2 -s 8 -t 4"):

    ext = os.path.splitext(file_l)[1]
    if ext == '.sdf':
        input_format_flag = '-isd'
    elif ext in ['.smi', '.txt']:
        input_format_flag = '-ismi'
    else:
        raise IOError("Format %s not recognized!"%(ext[1:]))

    suffix = (os.path.splitext(file_l)[0]).split('/')[-1]
    maefile = suffix + "_prep.mae"
    output_file = suffix + "_prep.mol2"

    # write ligprep command
    cmd = """ligprep -WAIT %(flags)s %(input_format_flag)s %(file_l)s -omae %(maefile)s
mol2convert -imae %(maefile)s -omol2 %(output_file)s"""%locals()

    script_name = 'run_ligprep.sh'
    with open(script_name, 'w') as file:
        script ="""#!/bin/bash
%(cmd)s"""% locals()
        file.write(script)
    os.chmod(script_name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IXUSR)

    # execute ligprep
    subprocess.check_output('./' + script_name +" &> ligprep.log", shell=True, executable='/bin/bash')
    mol2.update_mol2file(output_file, suffix + "_prep_.mol2", ligname='LIG', multi=True)

    nmol2files = len(glob.glob(suffix + "_prep_*.mol2"))
    output_files = []

    # assign partial charges using Antechamber
    for idx in range(nmol2files):
        mol2file = suffix + "_prep_%i.mol2"%(idx+1)
        mol2file_tmp = suffix + "_prep_%i_pc.mol2"%(idx+1)
        minimz.run_antechamber(mol2file, mol2file_tmp, at='sybyl', c='gas')
        shutil.move(mol2file_tmp, mol2file)
        output_files.append(os.path.abspath(mol2file))

    return output_files

def prepare_targets(input_files_r, jobid):

    if input_files_r:
        for file_r in input_files_r:
            ext = os.path.splitext(file_r)[1]
            if ext != '.pdb':
                raise ValueError("Only .pdb format for files with target is supported")

    if input_files_r:
        files_r = input_files_r
    else:
        achlysdir = os.path.realpath(__file__)
        dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data_cut'
        files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']

    workdir = 'job_' + jobid
    dir_r = workdir + '/targets'
    os.mkdir(dir_r)

    # copy files
    for idx, file_r in enumerate(files_r):
        new_file_r = 'target' + str(idx+1) + '.pdb'
        shutil.copyfile(file_r, dir_r+'/'+new_file_r)
