def die(msg, details=None):
    if msg:
        print("ERROR: " + msg)
    if details:
        print(details)
    raise SystemExit(1)


def warn(msg, details=None):
    print("WARNING: " + msg)
    if details:
        print(details)

def note(msg):
    print(msg)
