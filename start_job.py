import sys, os, socket

if len(sys.argv) != 3:
    print 'Usage: %s job_id chem_path' % (sys.argv[0])
    sys.exit()
    
job_id = sys.argv[1]
chem_path = sys.argv[2]

if socket.gethostname() == 'turtle.local':
    os.system('mkdir /Users/pwinter/Achlys/JOBS/%s' % job_id)
    os.system('cp /Users/pwinter/Achlys/git/AchlysBackEnd/tox.py /Users/pwinter/Achlys/JOBS/%s/' % job_id)
    os.chdir('/Users/pwinter/Achlys/JOBS/%s' % job_id)
    #print os.getcwd()
    os.system('python tox.py %s /Users/pwinter/Achlys/JOBS/%s/out.csv &' % (chem_path, job_id))
elif socket.gethostname() == 'silence':
    os.system('mkdir /home/achlys/JOBS/%s' % job_id)
    os.system('cp /home/achlys/AchlysBackEnd/tox.py /home/achlys/JOBS/%s/' % job_id)
    os.chdir('/home/achlys/JOBS/%s' % job_id)
    #print os.getcwd()
    os.system('python tox.py %s /home/achlys/JOBS/%s/out.csv &' % (chem_path, job_id))
else:
    print 'Unsupported system'
    sys.exit()
