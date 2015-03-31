#!/usr/bin/python

from __future__ import with_statement

import sys
import os
import subprocess
import tempfile
import shutil
import argparse
import ConfigParser
import numpy as np

known_programs = ['autodock', 'vina']

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

class DockingWorker(object):

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description="Run Achlys Docking")

        parser.add_argument('cpu_id',
            metavar='CPU ID',
            type=int,
            help='CPU ID')

        parser.add_argument('ncpus',
            metavar='number of cpus',
            type=int,
            help='total number of cpus used')

        parser.add_argument('nligs',
            metavar='number of ligands',
            type=int,
            help='total number of ligands')

        parser.add_argument('ntargets',
            metavar='number of targets',
            type=int,
            help='total number of targets')

        parser.add_argument('--multi',
            dest='multi',
            action='store_true',
            default=False,
            help='Run docking on multiple targets')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

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
# prepare receptor
prepare_receptor4.py -r target.pdb -o target.pdbqt

# run autogrid
prepare_gpf4.py -l ../lig.pdbqt -r target.pdbqt -o grid.gpf %(autogrid_options_flag)s
autogrid4 -p grid.gpf -l grid.glg

# run autodock
prepare_dpf4.py -l ../lig.pdbqt -r target.pbdqt -o dock.dpf -p move=../lig.pdbqt %(autodock_options_flag)s
autodock4 -p dock.dpf -l dock.dlg"""% locals()
                file.write(script)

        elif config.program == 'vina':

            # write vina config file
            with open('vina.config', 'w') as config_file:
                print >> config_file, 'receptor = target.pdbqt'
                print >> config_file, 'ligand = ../lig.pdbqt'
                for key in config.vina_options.keys():
                    print >> config_file, key + ' = ' + config.vina_options[key]

            # write vina script
            with open(script_name, 'w') as file:
                script ="""#!%(shebang)s

# prepare receptor
prepare_receptor4.py -r target.pdb -o target.pdbqt

# run vina
vina --config vina.config &>> vina.out"""% locals()
                file.write(script) 

    def run_docking(self, config):
    
        script_name = "run_" + config.program + ".sh"
        self.write_docking_script(script_name, config)
        subprocess.call("bash " + script_name, shell=True)

    def analyze_autodock_docking_results(self):

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
            with open("free_energy.txt", 'w') as fefile:
                print >> fefile, free_energy

            # (C) save the correct pose
            while "ATOM" not in line:
                line = dlgfile.next()
        
            with open('pose.pdb', 'w') as posefile:
                while "TER" not in line:
                    print >> posefile, line[:66]
                    line = dlgfile.next()
                print >> posefile, "END"

    def analyze_docking_results(self, config):

        if config.program == 'autodock':
            self.analyze_autodock_docking_results()
        elif config.program == 'vina':
            raise NotImplemented("Vina analyzing procedure not implemented")

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()    

        config = DockingConfig(args)

        ncpus = args.ncpus
        cpu_id = args.cpu_id
        nligs = args.nligs
        ntargets = args.ntargets

        curdir = os.getcwd()

        if cpu_id >= ncpus:
            raise IOError("CPU ID is supposed to be less than the number of CPUs")

        if args.multi:
            if ntargets != ncpus:
                raise ValueError("The number of targets should be equal to the number of CPUs")
            # prepare the ligand
            if config.program in ['autodock', 'vina']:
                subprocess.call("prepare_ligand4.py -l lig.pdb -o lig.pdbqt", shell=True)
            os.chdir('target%i'%cpu_id)
            # run docking
            self.run_docking(config)
            self.analyze_docking_results(config)
        else:
            # compute the idx of the ligands handled by the CPU
            idxs_lig = self.get_ligand_idxs(cpu_id, ncpus, nligs)
            for idx in idxs_lig:
               os.chdir('lig%i'%idx)
               # prepare the ligand
               if config.program in ['autodock', 'vina']:
                   subprocess.call("prepare_ligand4.py -l lig.pdb -o lig.pdbqt", shell=True)
               for jdx in range(ntargets):
                  os.chdir('target%i'%jdx)
                  # run docking
                  self.run_docking(config)
                  self.analyze_docking_results(config)
                  os.chdir('..')
               os.chdir(curdir)

if __name__=='__main__':
    DockingWorker().run()
