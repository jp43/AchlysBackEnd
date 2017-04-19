import os
import sys
import pandas as pd
import shutil
import subprocess

from math import sqrt
from glob import glob

key_residues = [('TYR', 652, [113, 241, 369, 497]), ('PHE', 656, [117, 245, 374, 501]), ('THR', 623, [84, 212, 340, 468])]

pose_dirs = glob('pose*/ligand')
nposes = len(pose_dirs)

pose_dirs = []
for idx in range(nposes):
    pose_dirs.append('pose%s/ligand'%(idx+1))

results = {}
for feature in ['pbsa', 'gbsa', 'pose_idx', 'dir']:
    results[feature] = []

# get MMPBSA/MMGBSA scores
for idx, dir in enumerate(pose_dirs):
    results['pose_idx'].append(idx+1)
    # initialize variables
    is_gbsa = False
    is_pbsa = False
    is_gbsa_section = False
    is_pbsa_section = False
    gbsa_score = None
    pbsa_score = None
    if os.path.isfile(dir+'/mmpbsa/mm.out'):
        with open(dir+'/mmpbsa/mm.out') as outf:
           for line in outf:
               if line.startswith('GENERALIZED BORN'):
                   is_gbsa = True
                   is_gbsa_section = True
               elif line.startswith('POISSON BOLTZMANN'):
                   is_pbsa = True
                   is_pbsa_section = True
               elif is_gbsa_section and line.startswith('DELTA TOTAL'):
                   gbsa_score = float(line.split()[2])
                   is_gbsa_section = False
               elif is_pbsa_section and line.startswith('DELTA TOTAL'):
                   pbsa_score = float(line.split()[2])
                   is_pbsa_section = False
    results['gbsa'].append(gbsa_score)
    results['pbsa'].append(pbsa_score)
    results['dir'].append(dir)

results = pd.DataFrame(results)
results['is_best_gbsa'] = results['gbsa'].apply(lambda x: x==results['gbsa'].min())
results['is_best_pbsa'] = results['pbsa'].apply(lambda x: x==results['pbsa'].min())

def dist_lig_to_residues(pdbfile, idxs):

    coords_l = []
    coords_r = []
    with open(pdbfile, 'r') as ff:
        for line in ff:
            if line.startswith(('ATOM','HETATM')):
                resname = str(line[17:20])
                residx = int(line[22:26])
                x, y, z = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                if resname == 'LIG':
                    coords_l.append([x, y, z])
                elif residx in idxs:
                    coords_r.append([x, y, z])
    dist2_min = 1e10
    for xl, yl, zl in coords_l:
        for xr, yr, zr in coords_r:
            dist2 = ((xl-xr)**2 + (yl-yr)**2 + (zl-zr)**2)
            if dist2 < dist2_min:
                dist2_min = dist2
    return sqrt(dist2_min)

pwd = os.getcwd()
for score in ['gbsa', 'pbsa']:
    # compute best PBSA and GBSA score
    row_best_score = results.loc[results[score].idxmin()]
    dir = row_best_score['dir']
    shutil.rmtree(score, ignore_errors=True)
    os.mkdir(score)
    os.chdir(score)
    with open(score+'.out', 'w') as gg:
        gg.write('%s score: '%(score.upper()) + '%.2f\n'%row_best_score[score])
        with open('cpptraj.in', 'w') as ff:
            ff.write("""parm ../%(dir)s/common/start.prmtop
trajin ../%(dir)s/md.dcd
strip :WAT,Na+,Cl-
rms first "@CA,C,N,O & !:LIG"
cluster ":LIG & !@/H" nofit mass epsilon 2.0 repout repout repfmt pdb summary summary.dat info info.dat\n"""%locals())
        subprocess.check_call('cpptraj -i cpptraj.in > cpptraj.log', shell=True, executable='/bin/bash')
        shutil.copyfile('repout.c0.pdb', score+'.pdb')
        for name, idx, residues_idxs in key_residues:
            dist = dist_lig_to_residues(score+'.pdb', residues_idxs)
            gg.write('Distance to %s%s: %.2f\n'%(name, idx, dist))
    os.chdir(pwd)
