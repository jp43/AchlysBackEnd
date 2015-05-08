from __future__ import with_statement

import sys
import os
import subprocess
import tempfile
import shutil
import re
import argparse
import logging
import time
import ConfigParser
import numpy as np

from achlys.kernel import docking

class DockingAnalysis(object):

    def __init__(self, args):

        self.ntargets = args.ntargets
        self.free_energy = np.zeros(self.ntargets)

        self.config = docking.DockingConfig(args.config_file)
        self.nposes = self.config.nposes

        if self.nposes > self.ntargets:
            raise docking.DockingConfigError("The number of final poses is larger than the total number of targets")

    def run(self):

        curdir = os.getcwd()
        for idx in range(self.ntargets):
            with open('target%i/free_energy.txt'%idx, 'r') as fefile:
                line = fefile.next().replace('\n','')
                self.free_energy[idx] = float(line)

        idxs_pose = np.argsort(self.free_energy)
        idxs_pose = idxs_pose[:self.config.nposes]
        np.savetxt('poses.txt', idxs_pose) # save indices of poses

        for idx, jdx in enumerate(idxs_pose):
            startdir = 'md-pose%i/startup'%idx
            os.makedirs(startdir)

            shutil.copyfile('target%i/pose.pdb'%jdx, startdir+'/pose.pdb')
            shutil.copyfile('target%i/target.pdb'%jdx, startdir+'/target.pdb')

            os.chdir(startdir)
            # remove hydrogens from target.pdb
            subprocess.call('babel -ipdb target.pdb -opdb target_ha.pdb -d', shell=True)

            with open('target_ha.pdb', 'r') as pdbfile:
                with open('complex.pdb', 'w') as cmplxfile:
                    for line in pdbfile:
                        if line.startswith('ATOM'):
                            newline = line.replace('\n','')
                            print >> cmplxfile, newline
                            if 'OXT' in newline:
                                print >> cmplxfile, 'TER'

            # add hydrogens to pose.pdb
            subprocess.call('babel -ipdb pose.pdb -opdb pose_h.pdb -h', shell=True)

            # estimate the ligand net charge from pose_h.pbd
            subprocess.call("antechamber -i pose_h.pdb -fi pdb -o pose_h.prepin -fo prepi \
               -j 4 -at gaff -c gas -du y -s 1 -pf y > antchmb.log", shell=True)
            
            net_charge = 0
            with open("antchmb.log", 'r') as logfile:
                for line in logfile:
                    if 'Gasteiger' in line:
                        net_charge = float(re.search(r'\((.*)\)', line).group(1))
            
            with open("charge.txt", 'w') as cfile:
                print >> cfile, net_charge
 
            # use Antichamber twice to create a .pdb file with correct numbers
            subprocess.call("antechamber -i pose_h.pdb -fi pdb -o pose_h.prepin -fo prepi \
               -j 4 -at gaff -c gas -du y -s 1 -pf y -nc %.1f > antchmb.log"%net_charge, shell=True)
                                
            subprocess.call("antechamber -i pose_h.prepin -fi prepi -o pose_h_1.pdb -fo pdb \
               -j 4 -at gaff -c gas -du y -s 1 -pf y -nc %.1f > antchmb.log"%net_charge, shell=True)

            with open('pose_h_1.pdb', 'r') as pdbfile:
                with open('lig.pdb', 'w') as cmplxpdbfile:
                    with open('complex.pdb', 'a') as cmplxfile:
                        for line in pdbfile:
                            if line.startswith('ATOM'):
                                newline = line.replace('\n','')
                                print >> cmplxpdbfile, "HETATM" + newline[6:]
                                print >> cmplxfile, "HETATM" + newline[6:]
                        print >> cmplxpdbfile, "END"
                        print >> cmplxfile, "END"

            tmpfiles = ['pose.pdb', 'pose_h.prepin', 'pose_h.pdb', 'pose_h_1.pdb', 'target.pdb', 'target_ha.pdb']

            # remove intermediate files
            for tmp in tmpfiles:
                os.remove(tmp)

            os.chdir(curdir)

class DockingAnalysisExe(object):

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description="Run Achlys Docking")

        parser.add_argument('ntargets',
            metavar='number of targets',
            type=int,
            help='total number of targets')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        return parser

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()

        logging.basicConfig(filename='achlys.log',
                            filemode='a',
                            format="%(levelname)s:%(name)s:%(asctime)s: %(message)s",
                            datefmt="%H:%M:%S",
                            level=logging.DEBUG)

        tcpu1 = time.time()
        logging.info('Starting docking analysis...')
     
        DockingAnalysis(args).run()

        tcpu2 = time.time()
        logging.info('Docking analysis done. Total time needed: %i s.' %(tcpu2-tcpu1))
