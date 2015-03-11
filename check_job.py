import sys, os, socket, os.path

if len(sys.argv) != 2:
    print 'Usage: %s job_id' % (sys.argv[0])
    sys.exit()
    
job_id = sys.argv[1]

if socket.gethostname() == 'turtle.local':
    if os.path.isfile('/Users/pwinter/Achlys/JOBS/%s/DONE' % job_id):
        print 'status=DONE'
        print 'results_path=/Users/pwinter/Achlys/JOBS/%s/DONE' % job_id
    else:
        print 'status=RUNNING'
elif socket.gethostname() == 'silence':
    if os.path.isfile('/home/achlys/JOBS/%ss/DONE' % job_id):
        print 'status=DONE'
        print 'results_path=/Users/pwinter/Achlys/JOBS/%s/DONE' % job_id
    else:
        print 'status=RUNNING'
else:
    print 'Unsupported system'
    sys.exit()
