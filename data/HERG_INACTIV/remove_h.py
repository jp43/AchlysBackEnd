import os
import sys

for i in range(7):
    with open('herg_000%i.pdb'%(i+1)) as pdbf:
        with open('herg_noh_000%i.pdb'%(i+1), 'w') as pdbf2:
            for line in pdbf:
                if line.startswith('ATOM'):
                    if not line[11:18].strip(' ').startswith('H'):
                        print >> pdbf2, line.replace('\n','')
                elif line.startswith(('TER','END')):
                    print >> pdbf2, line.replace('\n','')
