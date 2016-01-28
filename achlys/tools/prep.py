import sys
import os
import shutil
import ConfigParser
import time
import glob
import shutil
import subprocess

from achlys.tools import struct_tools

ligprep_default_options = {'tautomerizer': False, 'ring_conf': False, 'stereoizer': False, 'tarfiles': False, 'ionization': '0'}

# the first element of each tuple corresponds to the value True or False when the flag applies
ligprep_bool_flags = {'tautomerizer': (False, '-nt'), 'ring_conf': (False, '-nr'), 'stereoizer': (False, '-ns'), 'tarfiles': (False, '-nz')}
ligprep_value_flags = {'ionization': '-i'}

known_formats = ['.pdb', '.sdf', '.smi', '.txt']
known_systems = ['herg', 'herg-cut', 'herg-inactivated']

def check_ligand_files(files):

    for ff in files:
        if not os.path.isfile(ff):
            raise IOError("file " %ff + " does not exist!")
        ext = os.path.splitext(ff)[1]
        if ext not in known_formats:
            raise ValueError("format of input files should be among " + ", ".join(known_formats))

def prepare_ligand_structures(lig_files, jobID, config):

    if config.has_section('LIGPREP'):
        ligprep_options = dict(config.items('LIGPREP'))
    else:
        ligprep_options = {}

    # set defaults options if they are not mentionned in the config file
    for key, value in ligprep_default_options.items():
        if key not in ligprep_options:
            ligprep_options[key] = value

    # construct the command to execute ligprep
    ligprep_flags_str = ""
    for key, value in ligprep_options.items():
        if key in ligprep_bool_flags:
            if value == ligprep_bool_flags[key][0]:
                ligprep_flags_str += ligprep_bool_flags[key][1] + " "
        elif key in ligprep_value_flags:
            ligprep_flags_str += ligprep_value_flags[key] + " " + str(value) + " "
        else:
            raise ValueError("Option %s does not look to be a ligprep option!"%key)

    shift = 0
    for ff in lig_files:
        ext = os.path.splitext(ff)[1]
        if ext in ['.sdf', '.smi', '.txt']:
            # use ligprep if file are in .sdf or .smi formats to generate 3D structures
            outputfile = generate_3D_structure(ff, jobID, ligprep_flags_str)
            babel_input_flag = '-isdf'
        elif ext == '.pdb':
            # convert .pdb file to SDF format (assuming the structure is 3D)
            outputfile = os.path.basename(ff)
            shutil.copyfile(ff,'job_%s/%s'%(jobID, outputfile))
            babel_input_flag = '-ipdb'

        suffix = os.path.splitext(outputfile)[0]
        outputpdbfile = os.path.splitext(outputfile)[0] + '_.pdb'
        # generate PDB files
        subprocess.call('babel %s job_%s/%s -opdb job_%s/%s -m 2>/dev/null'%(babel_input_flag,jobID,outputfile,jobID,outputpdbfile), shell=True)

        nligs = 0
        for pdbfile in glob.glob('job_%s/'%jobID + suffix + '_*.pdb'):
            ligid = int((pdbfile.split('_')[-1]).split('.')[0]) - 1 + shift
            ligdir = 'job_%s/'%jobID + 'lig%i'%ligid

            # get ligand original name
            with open(pdbfile) as pdbf:
                line = pdbf.next().strip()
                if line.startswith('COMPND') and len(line) > 6:
                    ligname = line[6:].strip()
                else:
                    ligname = ''

            os.mkdir(ligdir)
            # copy original file in ligand directory
            shutil.copyfile(ff, ligdir + '/' + os.path.basename(ff))
            # write ligand name in lig.info
            with open(ligdir + '/lig.info', 'w') as infof:
                print >> infof, "Ligand orginal name: " + ligname 
                print >> infof,  "Original file: " + os.path.basename(ff)

            with open(ligdir + '/step.out', 'w') as f:
                print >> f, "start step 1 (docking)"

            shutil.move(pdbfile, ligdir+'/lig%s.pdb'%ligid)
            nligs += 1

        os.remove('job_%s/%s'%(jobID, outputfile))
        shift += nligs 

def generate_3D_structure(ff, jobID, flags):

    ext = os.path.splitext(ff)[1]
    if ext == '.sdf':
        inputflag = '-isd'
    elif ext in ['.smi', '.txt']:
        inputflag = '-ismi'

    suffix = (os.path.splitext(ff)[0]).split('/')[-1]
    outputfile = suffix + "_3D.sdf"

    with open('ligprep.sh', 'w') as file:
        script ="""#!/bin/bash
export SCHRODINGER=/opt/schrodinger2014-4
export PATH="$SCHRODINGER:$PATH"

ligprep %(inputflag)s %(ff)s -osd job_%(jobID)s/%(outputfile)s %(flags)s"""% locals()
        file.write(script)

    output = subprocess.check_output('bash ligprep.sh', shell=True)
    ligprepID = output.split()[-1]  

    # wait for output
    while True:
        output = subprocess.check_output('jobcontrol -list', shell=True)
        if ligprepID in output:
            time.sleep(2) 
        else:
            break

    for logf in glob.glob(suffix + '*.log'):
       os.remove(logf)
    os.remove('ligprep.sh')

    return outputfile

def prepare_targets(input_files_r, jobid, config):

    # check files related to the targets
    if input_files_r:
        input_files_r = input_files_r
        # get extension if file names provided are correct
        ext_r = self.get_format(input_files_r)
        if ext_r == '.pdb':
            ntargets = len(input_files_r)
        else:
            raise ValueError("Only .pdb format is supported now for files containing receptors")
    else:
        # look for an option in the config file
        if config.has_option('GENERAL', 'system'):
            system = config.get('GENERAL', 'system').lower()
            if system not in known_systems:
                raise StartJobError("The system specified in the configuration file should be one of " + ", ".join(known_systems))
            if system == 'herg':
                achlysdir = os.path.realpath(__file__)
                dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data'
                input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                ntargets = len(input_files_r)
                ext_r = '.pdb'
            elif system == 'herg-cut':
                achlysdir = os.path.realpath(__file__)
                dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data_cut'
                input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                ntargets = len(input_files_r)
                ext_r = '.pdb'
            elif system == 'herg-inactivated':
                achlysdir = os.path.realpath(__file__)
                dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data_inactiv'
                input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                ntargets = len(input_files_r)
                ext_r = '.pdb'
        else:
            raise ValueError('No files for targets provided')

    #copy targets
    workdir = 'job_' + jobid
    dir_r = workdir + '/targets'
    os.mkdir(dir_r)
    for idx, file_r in enumerate(input_files_r):
        shutil.copyfile(file_r,dir_r+'/target%i'%idx+ext_r)



## Convert SDF to 3D PDB file
#def convert_sdf_to_pdb(inpath, outpath):
#    cmd = '(babel -isdf %s -ch --gen3D ---errorlevel 1 -opdb %s 2>/dev/null ; echo $? > convert_pdb_status)' % (inpath, outpath)
#    os.system(cmd)
#
## Output SDF to PNG image file
#def convert_sdf_to_png(inpath, outpath):
#    cmd = '(babel -isdf %s -d ---errorlevel 1 -opng %s 2>/dev/null ; echo $? > convert_png_status)' % (inpath, outpath)
#    os.system(cmd)
#
#def convert_pdb_to_png(inpath, outpath):
#    cmd = '(babel -ipdb %s -d ---errorlevel 1 -opng %s 2>/dev/null ; echo $? > convert_png_status)' % (inpath, outpath)
#    os.system(cmd)
#
#def submit_prep_job(jobid, lig_id, submit_on='local'):
#    
#    if submit_on != 'local':
#        print 'Unsupported system for prep job'
#        sys.exit(1)
#        
#    os.chdir('lig%d' % lig_id)
#
#    if os.path.exists('lig%d.sdf'%lig_id):
#        convert_sdf_to_png('lig%d.sdf'%lig_id,'lig%d.png'%lig_id)
#        convert_sdf_to_pdb('lig%d.sdf'%lig_id,'lig%d.pdb'%lig_id)        
#    elif os.path.exists('lig%d.pdb'%lig_id):
#        convert_pdb_to_png('lig%d.pdb'%lig_id,'lig%d.png'%lig_id)
#
#    os.chdir('..')
#    return 'running'
#
#def check_prep_job(jobid, lig_id, submit_on='local'):
#    
#    if submit_on != 'local':
#        raise ValueError('Unsupported system for prep job')
#
#    os.chdir('lig%d' % lig_id)
#
#    status = 'done'
#    #if(os.path.exists('convert_pdb_status')):
#    #    with open ("convert_pdb_status", "r") as myfile:
#    #        if myfile.read().strip() == '0':
#    #            status = 'done'
#    #        else:
#    #            status = 'error'
#    #else:
#    #    if status != 'error':
#    #        status = 'running'
#    os.chdir('..')
#
#    return status
#
#
#class PrepWorker(object):
#
#    config = ConfigParser.SafeConfigParser()
#    config.read(args.config_file)
#
#    if config.has_section('LIGPREP'):
