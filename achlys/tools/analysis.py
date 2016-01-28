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
            self.chains = ['A', 'B', 'C', 'D']
            self.resIDs = [652, 656, 623]
            self.nresidues = len(self.resnames)
            if system == 'herg':
                # names and RSN of key residues
                self.rresIDs = [[239, 494, 749, 1004], [243, 498, 753, 1008], [210, 465, 720, 975]]
                self.shift = 652 - 239
                self.shift_m = 255
            elif system == 'herg-cut':
                # RSN of key residues
                self.rresIDs = [[113, 241, 369, 497], [117, 245, 374, 501], [84, 212, 340, 468]]
                self.shift = 652 - 113
                self.shift_m = 128
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
strip :WAT,Na+,Cl-
trajout mob-nowater.pdb pdb
"""% locals()
            file.write(script)

    def adjust_numbering_pdb(self, filename, config):
        """update numbering of residues in PDB file to meet common convention"""

        # works only because the residue numbers are always < 10000
        not_from_protein = ['LIG', 'WAT', 'Na+', 'Cl-']

        idx_m = 0
        idx_c = 0
        pdbtmp = 'tmp.pdb'
        with open(filename, 'r') as pdb1:
            with open(pdbtmp, 'w') as pdb2:
                for line in pdb1:
                    if line.startswith(('ATOM', 'HETATM')):
                        resname = line[17:20].strip()
                        if resname in not_from_protein:
                            newline = line
                        else:           
                            index = int(line[22:26])
                            index +=  config.shift - config.shift_m*idx_m
                            index_s = str(index)
                            if idx_c < len(config.chains):
                                chain_ID = config.chains[idx_c]
                            else:
                                chain_ID = ' '
                            newline = line[:21] + chain_ID + (4-len(index_s)) * ' ' + index_s + line[26:]
                    elif line.startswith('TER'):
                        idx_m = min(3, idx_m + 1)
                        idx_c += 1 
                        newline = 'TER\n'
                    else: 
                        newline = line
                    pdb2.write(newline)

        shutil.move('tmp.pdb', filename)

    def get_strip_pdb(self, pdbin, pdbout, distance, config):

        distance_s = distance**2
        # get coordinates of ligand
        coords_lig = []
        with open(pdbin, 'r') as pdbf:
            for line in pdbf:
                if line.startswith(('ATOM', 'HETATM')):
                    resname = line[17:20].strip()
                    if resname == 'LIG':
                        coords_lig.append(map(float, [line[30:38], line[38:46], line[46:54]]))
        coords_lig = np.array(coords_lig)

        resID_c = 0
        lines = ''
        write_coords = False 

        with open(pdbin, 'r') as pdb1:
            with open(pdbout, 'w') as pdb2:
                for line in pdb1:
                    if line.startswith(('ATOM', 'HETATM')):
                        # get residue ID
                        resID = int(line[22:26].strip())
                        if resID == resID_c: # same residue
                            lines += line
                        else: # the residue has changed
                            if write_coords:
                              pdb2.write(lines)
                            lines = line
                            write_coords = False
                        coords_atoms = np.array(map(float, [line[30:38], line[38:46], line[46:54]]))
                        value_s = np.min(np.sum((coords_lig - coords_atoms)**2, axis=1))
                        if value_s < distance_s:
                            write_coords = True # write residue coords
                        resID_c = resID # update current residue
                    else:
                        if write_coords:
                            pdb2.write(lines)
                            lines = ''
                            write_coords = False
                        pdb2.write(line)


        oldline = ''         
        with open(pdbout, 'r') as pdb2:
            with open('tmp.pdb', 'w') as pdb3:
                for line in pdb2:
                    if line != oldline:
                        pdb3.write(line)
                    oldline = line

        shutil.move('tmp.pdb', pdbout)

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

        # copy pdb file of representative structure to lig directory
        pdbfile = glob.glob('mob.*.pdb')[0]
        self.adjust_numbering_pdb(pdbfile, config)
        #shutil.copyfile(pdbfile, '../../mob-full.pdb')

        config_file_name = 'cpptraj.strip.in'
        self.prepare_cpptraj_striping_input_file(config_file_name, config)
        subprocess.call("cpptraj -i " + config_file_name + " > cpptraj.strip.out", shell=True, executable='/bin/bash')

        self.adjust_numbering_pdb('mob-nowater.pdb', config)
        shutil.copyfile('mob-nowater.pdb', '../../mob.pdb')

        self.get_strip_pdb(pdbfile, '../../mob-bp.pdb', 20.0, config)

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
        self.get_representative_structure(config)   
        os.chdir(curdir)

        # write info in lig.info
        with open('lig2.info', 'w') as ff:
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
