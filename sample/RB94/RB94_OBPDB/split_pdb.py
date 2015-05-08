import os
for x in xrange(1,95):
    pipe = os.popen('babel -f%d -l%d -ipdb KB94_LP.pdb -opdb 2>/dev/null | grep COMPND' % (x, x))
    out = pipe.next()
    pipe.close()
    title = out.split()[1].strip()
    os.system('babel -f%d -l%d -ipdb KB94_LP.pdb -opdb %s.pdb 2>/dev/null' % (x, x, title))

