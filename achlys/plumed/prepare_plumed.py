import os 
import sys
import operator
import subprocess
import numpy as np

def get_atoms_coordinates(pdbfile, monomer, names=None, startswith=False, return_residues_numbers=False):

    atoms_idxs = []
    coords = []
    if return_residues_numbers:
        resnum = [] 
    
    with open(pdbfile, 'r') as pdb:
        for line in pdb:
            if line.startswith('ATOM'):
                atom = line[13:17].strip()     
                resname = line[17:20].strip()
                if names is None or (not startswith and atom in names) or (startswith and any([atom.startswith(name) for name in names])):
                    if (monomer == 'protein' and resname not in ['LIG', 'WAT', 'Na+', 'Cl-']) \
          or (monomer == 'ligand' and resname == 'LIG'):
                        atoms_idxs.append(int(line[6:11].strip())) 
                        coords.append(map(float, [line[30:38], line[38:46], line[46:54]]))                            
                        if return_residues_numbers:
                            resnum.append(int(line[22:26].strip()))

    if return_residues_numbers:
        output = (np.array(atoms_idxs, dtype=int), np.array(resnum), np.array(coords))
    else:
        output = (np.array(atoms_idxs, dtype=int), np.array(coords))
    return output

def get_secondary_structures(sumfile, delay=1):
    """ get secondary structures residues from .sum file (ptraj's secstruct output)"""

    secstruct = None
    secstructs = []
    secidxs_old = [0]*delay

    with open(sumfile, 'r') as sum:
        sum.next() # first line is a header
        for line in sum:
            data = line.split()
            resnum = int(data[0])
            propensities = map(float, data[1:])
            # get index of the secondary structure involved
            secidxs = [idx for idx in range(len(propensities)) if propensities[idx] > 0.5]
            if secidxs:
                secidx = secidxs[0]
                if any([secidx == secidx_old for secidx_old in secidxs_old]):
                    secstruct.append(resnum)
                else:
                    if secstruct is not None:
                        secstructs.append(secstruct)
                    secstruct = [resnum]
            else:
                secidx = 0
            secidxs_old.append(secidx)
            secidxs_old = secidxs_old[1:]

    return secstructs

## (A) get reference points: receptor

atoms_names_r = ['CA','C','N','O']
atoms_names_r_str = ','.join(atoms_names_r)

# get coordinates of protein heavy atoms
atoms_idxs_r, resnum_r, coords_r = get_atoms_coordinates('start.pdb', 'protein', names=atoms_names_r, return_residues_numbers=True)
natoms_r = len(atoms_idxs_r)
nres_r = resnum_r[-1]

# get coordinates of the ligand
atoms_idxs_l, coords_l = get_atoms_coordinates('start.pdb', 'ligand')
natoms_l = len(atoms_idxs_l)

# heavy atom fluctuations of the protein
with open('cpptraj.in', 'w') as file:
    script ="""parm start.prmtop
parm start.prmtop
trajin start.pdb
secstruct :1-%(nres_r)s out secstruct"""% locals()
    file.write(script)

subprocess.call('cpptraj -i cpptraj.in > cpptraj.out',shell=True)
secstructs = get_secondary_structures('secstruct.sum', delay=2)

# get the minimal distances between each heavy atom and the ligand
mindists = np.zeros(natoms_r)
for idx, coord_r in enumerate(coords_r):
    mindist = 1e10
    for coord_l in coords_l:
        dist = np.sqrt(np.sum((coord_l - coord_r)**2))
        mindist = min(dist, mindist)
    mindists[idx] = mindist

nnatoms = 80 # number of nearest atoms chosen
nearest_atoms_idxs = np.argsort(mindists)
nearest_atoms_idxs = nearest_atoms_idxs[:nnatoms]

# heavy atom fluctuations of the protein
with open('cpptraj.in', 'w') as file:
    script ="""parm start.prmtop
trajin md.dcd
atomicfluct out atomfluct.apf :1-%(nres_r)s@%(atoms_names_r_str)s
select :1-%(nres_r)s@%(atoms_names_r_str)s"""% locals()
    file.write(script)

subprocess.call('cpptraj -i cpptraj.in > cpptraj.out',shell=True)
os.remove('cpptraj.in')

# double check atoms selected
f = open('cpptraj.out','r')
for line in f:
    if line.startswith('Selected='):
        atoms_idxs2_r = [idx+1 for idx in map(int,line.split()[1:])]
f.close()

for idx in range(natoms_r):
    if atoms_idxs_r[idx] != atoms_idxs2_r[idx]:
        raise ValueError("Atom numbers at line %i in start.pdb and in ptraj's output do not match!"%idx)
os.remove('cpptraj.out')

# heavy atom fluctuations of the protein
with open('cpptraj.in', 'w') as file:
    script ="""parm start.prmtop
trajin md.dcd
atomicfluct out atomfluct.apf :1-%(nres_r)s@%(atoms_names_r_str)s
select :1-%(nres_r)s@%(atoms_names_r_str)s"""% locals()
    file.write(script)

subprocess.call('cpptraj -i cpptraj.in > cpptraj.out',shell=True)
os.remove('cpptraj.in')
os.remove('cpptraj.out')

apf = np.loadtxt('atomfluct.apf')
atoms_flucts = apf[:,1]

# get the atomic fluctuations of the nearest atoms
nearest_atoms_flucts = atoms_flucts[nearest_atoms_idxs]

nnnatoms = 30 # final number of atoms wanted
# compute the indices that would sort "nearest_atoms_flucts"
rigid_atoms_sort_idxs = np.argsort(nearest_atoms_flucts)
rigid_atoms_sort_idxs = rigid_atoms_sort_idxs[:nnnatoms]

# get the indices of the corresponding atoms in the list of heavy atoms
rigid_atoms_idxs_ha = nearest_atoms_idxs[rigid_atoms_sort_idxs]
rigid_atoms_idxs = atoms_idxs_r[rigid_atoms_idxs_ha] # idxs in all atom configurations

# get secondary structures of closest atoms:
nearest_atoms_secstructs_idxs = []
for idx in range(nnnatoms):
    resnum = resnum_r[rigid_atoms_idxs_ha[idx]]
    is_secstruct = False
    for jdx, struct in enumerate(secstructs):
        if resnum in struct:
            nearest_atoms_secstructs_idxs.append(jdx)
            is_secstruct = True
    if not is_secstruct:
        nearest_atoms_secstructs_idxs.append('')

natoms_secstructs_dict = {}

for idx in range(nnnatoms):
    secstruct_idx = nearest_atoms_secstructs_idxs[idx]
    natoms_secstructs_dict.setdefault(secstruct_idx,0)
    natoms_secstructs_dict[secstruct_idx] += 1

if '' in natoms_secstructs_dict.keys():
    del natoms_secstructs_dict['']

if len(natoms_secstructs_dict) >= 2:

    # select the secondary structures containing the largest number of nearest atoms
    sorted_natoms_secstructs_dict = sorted(natoms_secstructs_dict.items(), key=operator.itemgetter(1))
    big_secstructs_idxs = [sorted_natoms_secstructs_dict[-idx-1][0] for idx in range(2)]

    # get nearest atoms in heavy atoms
    nearest_secstructs_1_idxs_r = []
    nearest_secstructs_2_idxs_r = []
    for idx in range(nnnatoms):
        if nearest_atoms_secstructs_idxs[idx] == big_secstructs_idxs[0]:
            nearest_secstructs_1_idxs_r.append(rigid_atoms_idxs[idx])
        elif nearest_atoms_secstructs_idxs[idx] == big_secstructs_idxs[1]:
            nearest_secstructs_2_idxs_r.append(rigid_atoms_idxs[idx])
else:
    raise ValueError('Unable to find 2 close secondary structures!')

# prepare strings to write plumed.dat
nearest_secstructs_1_idxs_r_str = ','.join(map(str,nearest_secstructs_1_idxs_r))
nearest_secstructs_2_idxs_r_str = ','.join(map(str,nearest_secstructs_2_idxs_r))

## (B) get reference points: ligand

# heavy atom fluctuations of the ligand
with open('cpptraj.in', 'w') as file:
    script ="""parm start.prmtop
trajin md.dcd
atomicfluct out ligfluct.apf :LIG
select :LIG"""% locals()
    file.write(script)

subprocess.call('cpptraj -i cpptraj.in > cpptraj.out',shell=True)
os.remove('cpptraj.in')

# double check atoms selected
f = open('cpptraj.out','r')
for line in f:
    if line.startswith('Selected='):
        atoms_idxs2_l = [idx+1 for idx in map(int,line.split()[1:])]
f.close()

for idx in range(natoms_l):
    if atoms_idxs_l[idx] != atoms_idxs2_l[idx]:
        raise ValueError("Atom numbers at line %i in start.pdb and in ptraj's output do not match!"%idx)
os.remove('cpptraj.out')

apf = np.loadtxt('ligfluct.apf')
atoms_flucts_l = apf[:,1]

nnnatoms_l = min(7, natoms_l) # final number of atoms wanted
rigid_atoms_sort_idxs_l = np.argsort(atoms_flucts_l)
rigid_atoms_sort_idxs_l = rigid_atoms_sort_idxs_l[:nnnatoms_l]

# get the indices of the corresponding atoms
rigid_atoms_idxs_l = atoms_idxs_l[rigid_atoms_sort_idxs_l]

rigid_atom_1_l = atoms_idxs_l[0]
coord_rigid_atom_1_l = coords_l[rigid_atoms_sort_idxs_l[0]]

dist_from_rigid_atom_1_l = np.zeros(natoms_l)
for idx, coord in enumerate(coords_l):
    dist_from_rigid_atom_1_l[idx] = np.sqrt(np.sum((coord - coord_rigid_atom_1_l)**2))

nearest_atoms_idxs_l = np.argsort(dist_from_rigid_atom_1_l)
# the first index is the reference point itself:
for idx in nearest_atoms_idxs_l[2:]:
    if idx in rigid_atoms_sort_idxs_l:
        rigid_atom_2_l = atoms_idxs_l[idx]
        break

rigid_atoms_idxs_l = np.sort(rigid_atoms_idxs_l)
rigid_atoms_idxs_l_str = ','.join(map(str,np.sort(rigid_atoms_idxs_l)))

# write plumed file
with open('plumed.dat', 'w') as plmfile:
    script ="""#.dat plumed file for ligand-protein exploratory MetaD

UNITS LENGTH=A TIME=fs ENERGY=kj/mol

c1r: COM ATOMS=%(nearest_secstructs_1_idxs_r_str)s
c2r: COM ATOMS=%(nearest_secstructs_2_idxs_r_str)s
c1l: COM ATOMS=%(rigid_atoms_idxs_l_str)s

r: DISTANCE ATOMS=c1r,c1l
theta: TORSION ATOMS=c1r,c2r,%(rigid_atom_1_l)s,%(rigid_atom_2_l)s

# set a wall of 1 kcal/mol
UPPER_WALLS ARG=r AT=20.0 KAPPA=418.4 LABEL=uwall

# performs MetaDynamics
metad: METAD ARG=r,theta PACE=500 HEIGHT=1.2 SIGMA=0.3,0.15 FILE=HILLS BIASFACTOR=6.0 TEMP=310.0

PRINT STRIDE=100 ARG=r,theta FILE=COLVAR
"""% locals()
    plmfile.write(script)

