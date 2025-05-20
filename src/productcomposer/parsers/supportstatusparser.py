def parse_supportstatus(filename, supportstatus_override):
    with open(filename, 'r') as file:
        for line in file.readlines():
            a = line.strip().split(' ')
            supportstatus_override[a[0]] = a[1]