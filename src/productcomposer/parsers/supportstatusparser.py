from ..utils.loggerutils import (warn)

def parse_supportstatus(filename, supportstatus_override):
    with open(filename, 'r') as file:
        for line in file.readlines():
            a = line.strip().split(' ')
            if len(a) == 2:
                supportstatus_override[a[0]] = a[1]
            else:
                warn(f'wrong supportstatus line')
