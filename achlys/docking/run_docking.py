from __future__ import with_statement

import sys
import os
import socket
import subprocess
import tempfile
import shutil
import argparse
import ConfigParser
import logging
import stat
import time
import numpy as np

known_programs = ['autodock', 'vina']
known_extract_options = ['all', 'lowest', 'none']

class DockingConfigError(Exception):
    pass

class DockingConfig(object):

    def __init__(self, args):

        config = ConfigParser.SafeConfigParser()
        config.read(args.config_file)

        if config.has_option('DOCKING', 'program'):
            program = config.get('DOCKING', 'program').lower()
            if program not in known_programs:
                raise DockingConfigError("program option should be one of " + ", ".join(known_programs)) 
            self.program = program
        else:
            self.program = 'autodock'

        if self.program == 'autodock':
            # check autogrid options
            if config.has_section('AUTOGRID'):
                self.autogrid_options = dict(config.items('AUTOGRID'))
            else:
                self.autogrid_options = {}
            # check autodock options
            if config.has_section('AUTODOCK'):
                self.autodock_options = dict(config.items('AUTODOCK'))
            else:
                self.autodock_options = {}

        if self.program == 'vina':
            # check vina options
            if config.has_section('VINA'):
                self.vina_options = dict(config.items('VINA'))
            else:
                self.vina_options = {}

        if config.has_option('DOCKING', 'nposes'):
            self.nposes  = config.getint('DOCKING', 'nposes') 
        else:
            self.nposes = 7

        self.input_file_l = args.input_file_l
        self.input_file_r = args.input_file_r

        if args.extract.lower() in known_extract_options:
            self.extract = args.extract.lower()
        else:
            raise DockingConfigError("Extract option should be one of " + ", ".join(known_extract_options))

class DockingWorker(object):

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description="Run Achlys Docking")

        parser.add_argument('-l',
            type=str,
            dest='input_file_l',
            default='lig.pdb',
            help = 'Ligand coordinate file(s): .pdb, .sdf')

        parser.add_argument('-r',
            type=str,
            dest='input_file_r',
            default='target.pdb',
            help = 'Receptor coordinate file(s): .pdb')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        parser.add_argument('--extract',
            dest='extract',
            default='lowest',
            help='extract ligand conformations: all, lowest, none')

        return parser

    def get_ligand_idxs(self, cpu_id, ncpus, nligs):

        # compute the idx of the ligands handled by the CPU
        if nligs > ncpus:
            start = 0
            for idx in range(ncpus):
                nligscpu =  nligs/ncpus
                if idx < nligs%ncpus:
                   nligscpu += 1 # add an extra configuration
                end = start + nligscpu
                if idx == cpu_id:
                   idxs_lig = range(start,end)
                   break
                start = end
        else:
            idxs_lig = [cpu_id]

        return idxs_lig

    def write_docking_script(self, script_name, config, options=None, shebang='/bin/bash'):

        if config.program == 'autodock':
            autogrid_options_flag = ' '.join(['-p ' + key + '=' + config.autogrid_options[key] \
                for key in config.autogrid_options.keys()])
            autodock_options_flag = ' '.join(['-p ' + key + '=' + config.autodock_options[key] \
                for key in config.autodock_options.keys()])

            # write autodock script
            with open(script_name, 'w') as file:
                script ="""#!%(shebang)s

set -e
# generate .pdbqt files
prepare_ligand4.py -l lig.pdb -o lig.pdbqt
prepare_receptor4.py -r target.pdb -o target.pdbqt

# run autogrid
prepare_gpf4.py -l lig.pdbqt -r target.pdbqt -o grid.gpf %(autogrid_options_flag)s
autogrid4 -p grid.gpf -l grid.glg

# run autodock
prepare_dpf4.py -l lig.pdbqt -r target.pbdqt -o dock.dpf -p move=lig.pdbqt %(autodock_options_flag)s
autodock4 -p dock.dpf -l dock.dlg"""% locals()
                file.write(script)

        elif config.program == 'vina':

            # write vina config file
            with open('vina.config', 'w') as config_file:
                print >> config_file, 'receptor = target.pdbqt'
                print >> config_file, 'ligand = lig.pdbqt'
                for key in config.vina_options.keys():
                    print >> config_file, key + ' = ' + config.vina_options[key]

            # write vina script
            with open(script_name, 'w') as file:
                script ="""#!%(shebang)s

# generate .pdbqt files
prepare_ligand4.py -l lig.pdb -o lig.pdbqt
prepare_receptor4.py -r target.pdb -o target.pdbqt

# run vina
vina --config vina.config &>> vina.out"""% locals()
                file.write(script) 

        print "-----------"
        print "HOSTNAME: ", socket.gethostname()
        print "-----------"
         
        os.chmod(script_name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IXUSR)

    def run_docking(self, config):
    
        script_name = "run_" + config.program + ".sh"

        self.write_docking_script(script_name, config)
        subprocess.call("./" + script_name)

    def analyze_autodock_docking_results(self, config):

        if config.extract == 'lowest':

            hist = []
            with open('dock.dlg', 'r') as dlgfile:
                # (A) get the index of the most populated cluster
                line = dlgfile.next()
                while "CLUSTERING HISTOGRAM" not in line:
                    line = dlgfile.next()
                nlines_to_skip = 8
                for idx in range(nlines_to_skip):
                    dlgfile.next()
                while True:
                    line = dlgfile.next()
                    if line[0] == '_':
                        break
                    hist.append(int(line.split('|')[4].strip()))
                cluster_idx = np.argmax(np.array(hist))+1

                # (B) get the lowest binding free energy
                while "Cluster Rank = %i"%cluster_idx not in line:
                    oldline = line # do backup 
                    line = dlgfile.next()
                run_idx = int(oldline.split('=')[1])
                nlines_to_skip = 4
                for idx in range(nlines_to_skip):
                    dlgfile.next()
                line = dlgfile.next()
                free_energy = float(line[48:53])
                
                # save the binding free energy
                with open("affinity.dat", 'w') as fefile:
                    print >> fefile, free_energy

                # (C) save the correct pose
                while "ATOM" not in line:
                    line = dlgfile.next()
 
                with open('lig_out.pdb', 'w') as posefile:
                    while "TER" not in line:
                        print >> posefile, 'ATOM  ' + line[6:66]
                        line = dlgfile.next()
                    print >> posefile, "END"

        elif config.extract == 'all':
            with open('dock.dlg', 'r') as dlgfile:

                with open("affinity.dat", 'w') as fefile:
                    with open('lig_out.pdb', 'w') as posefile:
                       isconf = False 
                       for line in dlgfile:

                          if line.startswith('DOCKED:'):
                              isconf = True
                              # (A) save binding energy
                              if 'Free Energy of Binding' in line:
                                 free_energy = float(line[53:61])
                                 print >> fefile, free_energy

                              # (B) save atom coordinates
                              if line[8:].startswith(('ATOM','HETATM')):
                                 print >> posefile, 'ATOM  ' + line[14:74]
                          elif isconf: # done with the current pose
                              isconf = False
                              print >> posefile, 'END'

        if config.extract in ['lowest', 'all']:
            self.prepare_ligand(config)

    def analyze_vina_docking_results(self, config):

        if config.extract in ['lowest', 'all']:
            with open('lig_out.pdbqt','r') as pdbqtfile:

                with open('lig_out.pdb', 'w') as posefile:
                    with open('affinity.dat', 'w') as fefile:

                        for line in pdbqtfile:
                            if line.startswith(('ATOM', 'HETATM')):
                                print >> posefile, 'ATOM  ' + line[6:66]
                            elif line.startswith('REMARK VINA RESULT:'):
                                free_energy=float(line[19:].split()[0])
                                print >> fefile, free_energy
                            elif line.startswith('ENDMDL'):
                                print >> posefile, 'END'
                                if config.extract == 'lowest':
                                    break

            self.prepare_ligand(config)

    def prepare_ligand(self, config):
        """Prepare ligands for Amber/NAMD simulations"""

        eh, pdbfile_tmp = tempfile.mkstemp(suffix='.pdb')
        fh, pdbfile_h_tmp = tempfile.mkstemp(suffix='.pdb')
        gh, pdbfile_h_1_tmp = tempfile.mkstemp(suffix='.pdb')

        with open('lig_out.pdb', 'r') as ligf:
            with open('lig_out_h.pdb', 'w') as lighf:
                with open('complex.pdb', 'w') as cmplxf:

                    isconf = False
                    for line in ligf:
                        if not isconf:
                            isconf = True
                            g = open(pdbfile_tmp, 'w')
                        if line.startswith(('ATOM', 'HETATM')):
                            g.write(line)

                        elif line.startswith('END'):
                            isconf = False
                            g.write('END')
                            g.close()
                            # (A) add hydrogens to extracted structure
                            subprocess.call('babel -ipdb ' + pdbfile_tmp + ' -opdb ' + pdbfile_h_tmp + ' -h', shell=True)
                            # (B) give unique name to atoms
                            self.give_unique_atom_names(pdbfile_h_tmp, pdbfile_h_1_tmp)
                            # (C) write target in complex.pdb
                            with open('target.pdb') as targtf:
                                for line_t in targtf:
                                    if line_t.startswith(('ATOM','HETATM')):
                                        newline = line_t.replace('\n','')
                                        print >> cmplxf, newline
                                    elif 'TER' in line_t:
                                        print >> cmplxf, 'TER'
                            # (D) write ligand in complex.pdb and lig_out_h.pdb
                            with open(pdbfile_h_1_tmp, 'r') as tmpf:
                                for line_t in tmpf:
                                    if line_t.startswith(('ATOM','HETATM')):
                                        lighf.write(line_t)
                                        cmplxf.write(line_t)
                                lighf.write('TER\nEND\n')
                                cmplxf.write('TER\nEND\n')

    def give_unique_atom_names(self, input_file, output_file):

        with open(input_file, 'r') as oldf:

            newf = open(output_file, 'w')
            known_atom_types = []
            atom_numbers = []

            for line in oldf:
                if line.startswith(('ATOM', 'HETATM')):

                    atom_type = line[12:14].strip()
                    if atom_type not in known_atom_types:
                        known_atom_types.append(atom_type)
                        atom_numbers.append(1)
                        newf.write(line)
                    else:
                        idx = known_atom_types.index(atom_type)
                        atom_number = str(atom_numbers[idx])
                        newf.write(line[:14]+atom_number+line[14+len(atom_number):])
                        atom_numbers[idx] += 1 

                elif line.startswith('END'):
                    newf.write('END\n')
                    newf.close() 

    def analyze_docking_results(self, config):

        if config.program == 'autodock':
            self.analyze_autodock_docking_results(config)
        elif config.program == 'vina':
            self.analyze_vina_docking_results(config)

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()    

        tcpu1 = time.time()

        print('Starting docking procedure...')
        config = DockingConfig(args)

        # run docking
        self.run_docking(config)
        self.analyze_docking_results(config)

        tcpu2 = time.time()
        print('Docking procedure done. Total time needed: %i s' %(tcpu2-tcpu1))

if __name__ == '__main__':
    DockingWorker().run()
