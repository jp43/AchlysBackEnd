from __future__ import with_statement

import sys
import os
import subprocess
import tempfile
import shutil
import argparse
import ConfigParser
import numpy as np

from achlys.kernel import docking

known_programs = ['namd']

class MDAchlysConfigError(Exception):
    pass

class MDAchlysConfig(object):

    def __init__(self, config_file):

        config = ConfigParser.SafeConfigParser()
        config.read(config_file)

        self.system = config.get('GENERAL', 'system').lower()

        if config.has_option('MD', 'program'):
            program = config.get('MD', 'program').lower()
            if program not in known_programs:
                raise DockingConfigError('program option should be one of ' + ', '.join(known_programs))
            self.program = program
        else:
            self.program = 'namd'

        if self.program == 'namd':
            if config.has_section('AMBER'):
                self.amber_options = dict(config.items('AMBER'))
            else:
                self.autodock_options = {}
            if config.has_section('NAMD'):
                self.namd_options = dict(config.items('NAMD'))
            else:
                self.namd_options = {}

        self.docking = docking.DockingConfig(config_file)

class MDAchlysWorker(object):

    def prepare_tleap_input_file(self, config, net_charge, options=None):

        nnas = int(148)
        ncls = int(136 + net_charge)

        # write tleap input file
        with open('leap.in', 'w') as file:
            script ="""source leaprc.ff99SB
source leaprc.gaff
loadamberprep lig.prepin
loadamberparams lig.frcmod
p = loadPdb complex.pdb
charge p
bond p.995.SG p.397.SG
bond p.907.SG p.230.SG
bond p.142.SG p.740.SG
bond p.652.SG p.485.SG
bond p.291.SG p.287.SG
bond p.797.SG p.801.SG
bond p.32.SG p.36.SG
bond p.542.SG p.546.SG
solvatebox p TIP3PBOX 10
addions p Na+ %(nnas)s Cl- %(ncls)s
charge p
saveAmberParm p start.prmtop start.inpcrd
savepdb p start.pdb
quit"""% locals()
            file.write(script)

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description='Run Achlys MD simulation..')

        parser.add_argument('cpu_id',
            metavar='CPU ID',
            type=int,
            help='CPU ID')

        parser.add_argument('ncpus',
            metavar='number of cpus',
            type=int,
            help='total number of cpus used per MD simulations')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        return parser

    def run_startup(self, args, config):

        curdir = os.getcwd()
        workdir = 'startup'
        os.chdir(workdir)

        if config.program in ['namd', 'amber']:
            # read net charge from charge.txt
            net_charge = np.loadtxt('charge.txt')
            # call antechamber
            subprocess.call('antechamber -i lig.pdb -fi pdb -o lig.prepin -fo prepi \
                -j 4 -at gaff -c gas -du y -s 1 -pf y -nc %.1f > antchmb.log'%net_charge, shell=True)
            # create starting structure
            subprocess.call('parmchk -i lig.prepin -f prepi -o lig.frcmod', shell=True)
            self.prepare_tleap_input_file(config, net_charge)
            subprocess.call('tleap -f leap.in', shell=True)

            # create ref-heat.pdb file
            with open('start.pdb', 'r') as startfile:
                with open('ref-heat.pdb', 'w') as refheatfile:
                    for line in startfile:
                        if line.startswith(('ATOM', 'HETATM')):
                            atom_name = line[12:16].strip()
                            res_name = line[17:20].strip()
                            if 'WAT' in res_name: # water molecules
                                newline = line[0:30] + '%8.3f'%0.0 + line[38:]
                            elif 'LIG' in res_name: # atoms of the ligand
                                if atom_name.startswith(('C', 'N', 'O')):
                                    newline = line[0:30] + '%8.3f'%50.0 + line[38:]
                                else:
                                    newline = line[0:30] + '%8.3f'%0.0 + line[38:]
                            else: # atoms of the protein
                                if atom_name in ['C', 'CA', 'N', 'O']:
                                    newline = line[0:30] + '%8.3f'%50.0 + line[38:]
                                else:
                                    newline = line[0:30] + '%8.3f'%0.0 + line[38:]
                        else:
                            newline = line
                        print >> refheatfile, newline.replace('\n','')
        os.chdir(curdir)

    def run_minimization(self, args, config):

        curdir = os.getcwd()
        workdir = 'min'
        shutil.rmtree(workdir, ignore_errors=True)
        os.mkdir(workdir)
        os.chdir(workdir)

        if config.program == 'namd':
            achlysdir = os.path.realpath(__file__)
            namddir = '/'.join(achlysdir.split('/')[:-6]) + '/share/params/namd'

            # use leap.log to find the dimensions of the box
            with open('../startup/leap.log', 'r') as logfile:
                for line in logfile:
                    line_s = line.strip()
                    if line_s.startswith('Total bounding box'):
                        box = map(float,line_s.split()[-3:])

            # prepare input file
            with open(namddir + '/min.conf', 'r') as minfile_ref:
                with open('min.conf', 'w') as minfile:
                    for line in minfile_ref:
                        if line.startswith('cellBasisVector1'):
                            print >> minfile, 'cellBasisVector1  %5.3f       0.0        0.0'%(box[0]+0.5)
                        elif line.startswith('cellBasisVector2'):
                            print >> minfile, 'cellBasisVector2    0.0       %5.3f      0.0'%(box[1]+0.5)
                        elif line.startswith('cellBasisVector3'):
                            print >> minfile, 'cellBasisVector3    0.0         0.0      %5.3f'%(box[2]+0.5)
                        else:
                            print >> minfile, line.replace('\n', '')

            subprocess.call('mpirun -np ' + str(args.ncpus) + ' namd2 min.conf', shell=True)

            # use ptraj to convert .dcd file to .pdb
            with open('ptraj.in', 'w') as prmfile:
                print >> prmfile, 'trajin  min.dcd 1 1 1'
                print >> prmfile, 'trajout run.pdb PDB'
            subprocess.call('ptraj ../startup/start.prmtop < ptraj.in > ptraj.out', shell=True)
            shutil.move('run.pdb.1', 'end-min.pdb')

        os.chdir(curdir)

    def run_heating(self, args, config):

        curdir = os.getcwd()
        workdir = 'heat'
        shutil.rmtree(workdir, ignore_errors=True)
        os.mkdir(workdir)
        os.chdir(workdir)

        if config.program == 'namd':
            achlysdir = os.path.realpath(__file__)
            namddir = '/'.join(achlysdir.split('/')[:-6]) + '/share/params/namd'

            shutil.copyfile(namddir + '/heat.conf','heat.conf')
            subprocess.call('mpirun -np ' + str(args.ncpus) + ' namd2 heat.conf', shell=True)

            # use ptraj to convert .dcd file to .pdb
            with open('ptraj.in', 'w') as prmfile:
                print >> prmfile, 'trajin heat.dcd 1 1 1'
                print >> prmfile, 'trajout run.pdb PDB'
            subprocess.call('ptraj ../startup/start.prmtop < ptraj.in > ptraj.out', shell=True)
            shutil.move('run.pdb.1', 'end-heat.pdb')

        os.chdir(curdir)

    def run_equilibration(self, args, config):

        curdir = os.getcwd()
        workdir = 'equ'
        shutil.rmtree(workdir, ignore_errors=True)
        os.mkdir(workdir)
        os.chdir(workdir)

        if config.program == 'namd':
            achlysdir = os.path.realpath(__file__)
            namddir = '/'.join(achlysdir.split('/')[:-6]) + '/share/params/namd'

            shutil.copyfile(namddir + '/equ.conf', 'equ.conf')
            subprocess.call('mpirun -np ' + str(args.ncpus) + ' namd2 equ.conf', shell=True)

            # use ptraj to extract the last frame  .dcd file to .pdb
            with open('ptraj.in', 'w') as prmfile:
                print >> prmfile, 'trajin equ.dcd 10 10 1'
                print >> prmfile, 'trajout run.pdb PDB'
            subprocess.call('ptraj ../startup/start.prmtop < ptraj.in > ptraj.out', shell=True)
            shutil.move('run.pdb.10', 'end-equ.pdb')

        os.chdir(curdir)

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()

        config = MDAchlysConfig(args.config_file)

        curdir = os.getcwd()
        workdir = 'md-pose%i'%args.cpu_id
        os.chdir(workdir)

        # (A) start-up
        self.run_startup(args, config)

        # (B) minization
        self.run_minimization(args, config)

        # (C) heating
        self.run_heating(args, config)

        # (D) equilibration
        self.run_equilibration(args, config)
