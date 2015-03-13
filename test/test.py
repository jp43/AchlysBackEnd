import csv, time

EPSILON = 0.1

master = open('master.csv')
master_dict = {}
master_reader = csv.reader(master)
master_reader.next()
for row in master_reader:
    name = row[0]
    affinity = float(row[1])
    distance = float(row[2])
    blocker = row[3]
    master_dict[name] = (affinity, distance, blocker)
master.close()

test = open('out.csv')
test_reader = csv.reader(test)
test_reader.next()
for row in test_reader:
    name = row[0]
    affinity = float(row[1])
    distance = float(row[2])
    blocker = row[3]
    master_affinity, master_distance, master_blocker = master_dict[name]
    if affinity - master_affinity > EPSILON:
        print '%s has affinities that aren\'t close' % name
    elif affinity != master_affinity:
        print '%s differs in affinity' % name
    if distance - master_distance > EPSILON:
        print '%s has distances that aren\'t close' % name
    elif distance != master_distance:
        print '%s differs in distance' % name
    if blocker != master_blocker:
        print '%s differs in blocker status' % name
test.close()
