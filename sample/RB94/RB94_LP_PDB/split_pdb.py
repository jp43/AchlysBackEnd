import sys, os

infn = sys.argv[1]

count = 94

for x in xrange(1,count):
    pipe = os.popen('babel -f%d -l%d -ipdb %s -opdb 2>/dev/null | grep COMPND' % (x, x, infn))
    out = pipe.next()
    pipe.close()
    title = out.split()[1].strip()
    os.system('babel -f%d -l%d -ipdb %s -opdb %s.pdb 2>/dev/null' % (x, x, infn, title))

