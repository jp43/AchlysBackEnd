from __future__ import with_statement

import sys
import os
import argparse
import ConfigParser
import numpy as np
import glob

from achlys.kernel import docking
from achlys.kernel import md
from achlys.kernel import mmpbsa

class AnalysisConfigError(Exception):
    pass

class AnalysisConfig(object):

    def __init__(self, config_file):

        config = ConfigParser.SafeConfigParser()
        config.read(config_file)

        self.distmax = config.getfloat('ANALYSIS', 'distmax')
        self.femax = config.getfloat('ANALYSIS', 'femax')
        self.docking = docking.DockingConfig(config_file)
        self.md = md.MDAchlysConfig(config_file)
        self.mmpbsa = mmpbsa.MMPBSAAchlysConfig(config_file)

class AnalysisWorker(object):

    def get_minimal_distance(self, config):

        if config.md.program == 'namd':
            filename = 'equ/end-equ.pdb'
        else:
            raise NotImplemented("analysis of results for MD software different than namd is not supported")

        if config.md.system == 'herg':
            # names and RSN of Thr's residues
            resIDs = [('THR', 210), ('THR', 465), ('THR', 720), ('THR', 975)]

        coords = []
        # get coordinates of specific residues
        with open(filename, 'r') as pdbfile:
            for line in pdbfile:
                if line.startswith(('ATOM', 'HETATM')):
                    name = line[17:20].strip()
                    index = int(line[22:26])
                    for ID in resIDs:
                        if name == ID[0] and index == ID[1]:
                            coords.append(map(float, [line[30:38], line[38:46], line[46:54]]))
                            break
        coords = np.array(coords)

        # get coordinates of the ligand
        coordslig = []
        with open(filename, 'r') as pdbfile:
            for line in pdbfile:
                if line.startswith(('ATOM', 'HETATM')):
                    name = line[17:20].strip()
                    if name == 'LIG':
                        coordslig.append(map(float, [line[30:38], line[38:46], line[46:54]]))

        coordslig = np.array(coordslig)
        mindist = 1e10
        for coordlig in coordslig:
            for coord in coords:
                dist = np.sqrt(np.sum((coordlig - coord)**2))
                mindist = min(dist, mindist)

        return mindist

    def get_binding_free_energy(self, config):

        mmpbsa_output_file = 'mmpbsa/mm.out'
        with open(mmpbsa_output_file, 'r') as mmfile:
            for line in mmfile:
                if line.startswith('DELTA TOTAL'):
                    binding_free_energy = float(line.split()[2])

        return binding_free_energy

    def run(self):

        parser = argparse.ArgumentParser(description='Run Achlys Analysis..')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        args = parser.parse_args()
        config = AnalysisConfig(args.config_file)
        curdir = os.getcwd()

        distance = []
        binding_free_energy = []

        for workdir in glob.glob('md-pose*'):
            os.chdir(workdir)
            distance.append(self.get_minimal_distance(config))
            binding_free_energy.append(self.get_binding_free_energy(config))
            os.chdir(curdir)

        binding_free_energy_idx = np.argmin(np.array(binding_free_energy))
        dist = distance[binding_free_energy_idx]
        binding_free_energy = binding_free_energy[binding_free_energy_idx]

        with open('status.txt', 'w') as statfile:
            if dist < config.distmax and binding_free_energy < config.femax:
                print >> statfile, 'status: BLOCKER' 
            else:
                print >> statfile, 'status: NON-BLOCKER'
            print >> statfile, 'distance: %8.3f' %dist
            print >> statfile, 'binding free energy: %8.3f' %binding_free_energy

