import sys
import os
import shutil
import subprocess
from achlys import struct_tools

# Convert SDF to 3D PDB file
def convert_sdf_to_pdb(inpath, outpath):
    cmd = '(babel -isdf %s -ch --gen3D ---errorlevel 1 -opdb %s 2>/dev/null ; echo $? > convert_pdb_status) &' % (inpath, outpath)
    os.system(cmd)

# Output SDF to PNG image file
def convert_sdf_to_png(inpath, outpath):
    cmd = '(babel -isdf %s -d ---errorlevel 1 -opng %s 2>/dev/null ; echo $? > convert_png_status) &' % (inpath, outpath)
    os.system(cmd)


def submit_prep_job(jobid, lig_id, submit_on='local'):
    
    if submit_on != 'local':
        print 'Unsupported system for prep job'
        sys.exit(1)
        
    os.chdir('lig%d' % lig_id)

    convert_sdf_to_png('lig%d.sdf' % lig_id, 'lig%d.png' % lig_id)
    convert_sdf_to_pdb('lig%d.sdf' % lig_id, 'lig%d.pdb' % lig_id)        

    os.chdir('..')


def check_prep_job(jobid, lig_id, submit_on='local'):
    
    if submit_on != 'local':
        print 'Unsupported system for prep job'
        sys.exit(1)
        
    status = 'DONE'
    
    os.chdir('lig%d' % lig_id)

    if(os.path.exists('convert_png_status')):
        with open ("convert_png_status", "r") as myfile:
            if myfile.read().strip() == '0':
                status = 'DONE'
            else:
                status = 'ERROR'
    else:
        if status != 'ERROR':
            status = 'RUNNING'

    if(os.path.exists('convert_pdb_status')):
        with open ("convert_pdb_status", "r") as myfile:
            if myfile.read().strip() == '0':
                status = 'DONE'
            else:
                status = 'ERROR'
    else:
        if status != 'ERROR':
            status = 'RUNNING'

    os.chdir('..')

    return status

