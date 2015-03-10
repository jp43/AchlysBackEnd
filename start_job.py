import sys, os

if len(sys.argv) != 3:
    print 'Usage: %s job_id chem_path' % (sys.argv[0])
    sys.exit()
    
job_id = sys.argv[1]
chem_path = sys.argv[2]

os.system('mkdir /home/achlys/JOBS/%s' % job_id)
os.system('cp /home/achlys/AchlysBackEnd/tox.py /home/achlys/JOBS/%s/' % job_id)
os.chdir('/home/achlys/JOBS/%s' % job_id)
print os.getcwd()
os.system('python tox.py %s /home/achlys/JOBS/%s/out.csv' % (chem_path, job_id))
