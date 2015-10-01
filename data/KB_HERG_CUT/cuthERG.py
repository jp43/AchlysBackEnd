import os
import glob

for pdbfile in glob.glob('hERG-conformations_*.pdb'):
    atomidx = 0
    residx = 0
    oldresnum = 0
    targetidx = pdbfile[-6:-4]
    with open('hERG-conformations-cut_%s.pdb'%targetidx,'w') as pdbfo:
        with open(pdbfile, 'r') as pdbf:
            for line in pdbf:
                if line.startswith('ATOM'):
                    resnum = int(line[22:26])
                    if (resnum >= 127 and resnum < 255) or (resnum >= 382 and resnum < 510) or (resnum >= 637 and resnum < 765) or (resnum >= 892 and resnum < 1020):
                        doprint = True
                        if resnum in [127, 382, 637, 892]:
                            atomname = line[11:16].strip()
                            #print atomname
                            if atomname != 'H':
                                atomidx += 1
                                newline = line #line[:17] + 'ACE' + line[20:]
                            else:
                                doprint = False
                        elif resnum in [254, 509, 764, 1019]:
                            atomidx += 1
                            newline = line #line[:17] + 'NME' + line[20:]
                        else:
                            atomidx += 1
                            newline = line
                        if resnum != oldresnum: 
                            oldresnum = resnum
                            residx += 1
                        newline = newline[:6] + ' '*(5-len(str(atomidx))) + str(atomidx) + newline[11:]
                        newline = newline[:22] + ' '*(4-len(str(residx))) + str(residx)  + newline[26:]
                        if doprint:
                            print >> pdbfo, newline.replace('\n','')
                else:
                    print >> pdbfo, line.replace('\n','')
