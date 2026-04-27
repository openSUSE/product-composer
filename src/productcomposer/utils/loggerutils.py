from typing import NoReturn, Optional


def die(msg: Optional[str], details: Optional[str] = None) -> NoReturn:
    if msg:
        print("ERROR: " + msg, flush=True)
    if details:
        print(details, flush=True)
    raise SystemExit(1)


def warn(msg: str, details: Optional[str] = None) -> None:
    print("WARNING: " + msg, flush=True)
    if details:
        print(details, flush=True)

def note(msg):
    print(msg, flush=True)
