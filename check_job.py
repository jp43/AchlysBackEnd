import sys, os, socket, os.path

if len(sys.argv) != 2:
    print 'Usage: %s job_id' % (sys.argv[0])
    sys.exit()
    
job_id = sys.argv[1]

if socket.gethostname() == 'turtle.local':
    if os.path.isfile('/Users/pwinter/Achlys/JOBS/%s/DONE' % job_id):
        print 'status=DONE'
        print 'results_path=/Users/pwinter/Achlys/JOBS/%s/out.csv' % job_id
    elif os.path.isdir('/Users/pwinter/Achlys/JOBS/%s' % job_id):
        print 'status=RUNNING'
    else:
        print 'status=ERROR'
elif socket.gethostname() == 'silence':
    if os.path.isfile('/home/achlys/JOBS/%s/DONE' % job_id):
        print 'status=DONE'
        print 'results_path=/home/achlys/JOBS/%s/out.csv' % job_id
    elif os.path.isdir('/home/achlys/JOBS/%s' % job_id):
        print 'status=RUNNING'
    else:
        print 'status=ERROR'
else:
    print 'Unsupported system'
    sys.exit()
