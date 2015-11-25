from __future__ import with_statement

import sys
import os
import argparse
import subprocess
import shutil
import ConfigParser
import numpy as np
import time
import glob

known_programs = ['namd']
known_systems = ['herg', 'herg-cut', 'herg-inactivated']

class AnalysisConfigError(Exception):
    pass

class AnalysisConfig(object):

    def __init__(self, config_file):

        config = ConfigParser.SafeConfigParser()
        config.read(config_file)

        if config.has_option('GENERAL', 'nposes'):
            self.nposes = config.getint('GENERAL', 'nposes')
        else:
            self.nposes = 7
        
        self.keyres_idx = 2
        if config.has_option('GENERAL', 'system'):
            system = config.get('GENERAL', 'system').lower()
            self.resnames = ['TYR', 'PHE', 'THR']
            self.resIDs = [652, 656, 623]
            self.nresidues = len(self.resnames)
            if system == 'herg':
                # names and RSN of key residues
                self.rresIDs = [[239, 494, 749, 1004], [243, 498, 753, 1008], [210, 465, 720, 975]]
            elif system == 'herg-cut':
                # RSN of key residues
                self.rresIDs = [[113, 241, 369, 497], [117, 245, 374, 501], [84, 212, 340, 468]]
            elif system == 'herg-inactivated':
                pass

        self.distmax = config.getfloat('ANALYSIS', 'distmax')
        self.femax = config.getfloat('ANALYSIS', 'femax')

        if config.has_option('MD', 'program'):
            program = config.get('MD', 'program').lower()
            if program not in known_programs:
                raise MDConfigError('program option should be one of ' + ', '.join(known_programs))
            self.program = program
        else:
            self.program = 'namd'

        if self.program == 'namd':
            if config.has_section('AMBER'):
                self.amber_options = dict(config.items('AMBER'))
            else:
                self.amber_options = {}
            if config.has_section('NAMD'):
                self.namd_options = dict(config.items('NAMD'))
            else:
                self.namd_options = {}

        # check number of MD frames 
        self.nsteps = int(self.namd_options['nsteps'])
        self.outputfreq = int(self.namd_options['outputfreq'])

        self.nframes = self.nsteps/self.outputfreq

class AnalysisWorker(object):

    def prepare_cpptraj_input_file(self, filename, config):

        diststr = '\n'.join(["distance :LIG :%s@CA out dist.dat"%ID for IDs in config.rresIDs for ID in IDs])
        nframes = config.nframes
        nframesover2 = nframes/2

        # write cpptraj config file to compute distance with key residues
        with open(filename, 'w') as file:
            script ="""parm ../common/start.prmtop
trajin ../md.dcd %(nframesover2)s %(nframes)s 1
strip :WAT,Na+,Cl-
%(diststr)s
"""% locals()
            file.write(script)

    def prepare_cpptraj_clustering_input_file(self, filename, config):

        nframes = config.nframes

        # write cpptraj config file to cluster frames
        with open(filename, 'w') as file:
            script ="""parm ../common/start.prmtop
trajin ../md.dcd 1 %(nframes)s 1
rmsd align first "@CA,C,N & !:LIG"
rmsd rmsdlig first ":LIG & !@/H" nofit
cluster C1 data rmsdlig repout mob repfmt pdb averagelinkage clusters 1
"""% locals()
            file.write(script)

    def prepare_cpptraj_striping_input_file(self, filename, config):

        pdbfile = glob.glob('mob.*.pdb')[0]
        # write cpptraj config file to strip the mode of binding
        with open(filename, 'w') as file:
            script ="""parm ../common/start.prmtop
trajin %(pdbfile)s
mask "(:LIG<:4.0)" maskpdb mob.pdb
"""% locals()
            file.write(script)

    def get_distances_2_key_residues(self, config):

        config_file_name = 'cpptraj.kres.in'

        self.prepare_cpptraj_input_file(config_file_name, config)
        subprocess.call("cpptraj -i " + config_file_name + " > cpptraj.kres.out", shell=True, executable='/bin/bash')

        nresidues = config.nresidues
        dists = np.loadtxt('dist.dat')

        avgdists = []
        monomer_idxs = []

        # take the average distance to each key residue
        avg = np.mean(dists[:,1:], axis=0)

        # keep the mononer with the closest distance to the residue
        for idx in range(nresidues):
            avgdists_tmp = avg[4*idx:4*(idx+1)] 
            mononer_idx = np.argmin(avgdists_tmp)
            monomer_idxs.append(mononer_idx)
            avgdists.append(avgdists_tmp[mononer_idx])

        return avgdists

    def get_binding_free_energy(self, config):

        mmpbsa_output_file = 'mm.out'
        with open(mmpbsa_output_file, 'r') as mmfile:
            for line in mmfile:
                if line.startswith('DELTA TOTAL'):
                    binding_free_energy = float(line.split()[2])

        return binding_free_energy

    def get_representative_structure(self, config):

        config_file_name = 'cpptraj.clst.in'
        self.prepare_cpptraj_clustering_input_file(config_file_name, config)
        subprocess.call("cpptraj -i " + config_file_name + " > cpptraj.clst.out", shell=True, executable='/bin/bash')

        config_file_name = 'cpptraj.strip.in'
        self.prepare_cpptraj_striping_input_file(config_file_name, config)
        subprocess.call("cpptraj -i " + config_file_name + " > cpptraj.strip.out", shell=True, executable='/bin/bash')

    def run(self):

        parser = argparse.ArgumentParser(description='Run Achlys Analysis..')

        parser.add_argument('-f',
            dest='config_file',
            required=True,
            help='config file containing some extra parameters')

        args = parser.parse_args()

        config = AnalysisConfig(args.config_file)

        poseids = []
        for dir in glob.glob('pose*'):
            id = int(dir[4:])
            poseids.append(id)

        poseids.sort()
        lowestbfe = 0

        curdir = os.getcwd()
        for id in poseids:
            mmpbsadir = 'pose' + str(id) +'/mmpbsa'
            if os.path.isdir(mmpbsadir):
                os.chdir(mmpbsadir)
                bfe  = self.get_binding_free_energy(config)
                if bfe < lowestbfe:
                    lowestbfe = bfe
                    lowestbfe_id = id
                os.chdir(curdir)
        
        # compute distances to key residues
        os.chdir('pose' + str(lowestbfe_id) +'/mmpbsa')
        avgdists = self.get_distances_2_key_residues(config)

        # get representative structure from trajectory
        pdbfile = self.get_representative_structure(config)   
        # copy pdb file of representative structure to lig directory
        shutil.copyfile(curdir + "/pose" + str(lowestbfe_id) + '/mmpbsa/mob.pdb.1', curdir + '/mob.pdb')
        os.chdir(curdir)

        # write info in lig.info
        with open('lig.info', 'w') as ff:
             print >> ff, "Lowest binding energy: " + str(lowestbfe)
             print >> ff, "Pose no: " + str(lowestbfe_id)
             if lowestbfe < config.femax: 
                 print >> ff, "Ligand status: BLOCKER"
             else:
                 print >> ff, 'Ligand status: NON-BLOCKER'
             for idx in range(config.nresidues):
                 print >> ff, "Distance to " + str(config.resnames[idx]) + " " + str(config.resIDs[idx]) + ": %5.8f "%avgdists[idx]

if __name__ == '__main__':
    AnalysisWorker().run()
