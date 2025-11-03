from typing import NoReturn, Optional


def die(msg: Optional[str], details: Optional[str]=None) -> NoReturn:
    if msg:
        print("ERROR: " + msg)
    if details:
        print(details)
    raise SystemExit(1)


def warn(msg: str, details: Optional[str]=None) -> None:
    print("WARNING: " + msg)
    if details:
        print(details)

def note(msg):
    print(msg)
