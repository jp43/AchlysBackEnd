import os
import sys

for i in range(7):
    rsn = 0
    chainids = ['A', 'B', 'C', 'D']
    curidx = 0
    shiftrsn = 0
    atomnum = 0

    with open('herg0%i.pdb'%(i+1)) as pdbf:
        with open('herg_000%i.pdb'%(i+1), 'w') as pdbf2:
            for line in pdbf:
                if line.startswith('ATOM'):
                    rsn = str(int(line[22:26]) + shiftrsn)
                    rsn = ' '*(4-len(rsn)) + rsn
                    atomnum += 1
                    newline = line[:6] + str(' '*(5-len(str(atomnum)))+ str(atomnum)) + line[11:21] + chainids[curidx] + str(rsn) + line[26:66]
                    print >> pdbf2, newline.replace('\n','')
                elif line.startswith('TER'):
                    print >> pdbf2, 'TER'
                    shiftrsn = int(rsn)
                    curidx += 1 
            print >> pdbf2, 'TER'
            print >> pdbf2, 'END'
