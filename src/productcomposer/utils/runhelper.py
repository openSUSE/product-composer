import subprocess
from ..utils.loggerutils import (die, warn, note)

def run_helper(args, cwd=None, fatal=True, stdout=None, stdin=None, failmsg=None, verbose=False):
    if verbose:
        note(f'Calling {args}')
    if stdout is None:
        stdout = subprocess.PIPE
    if stdin is None:
        stdin = subprocess.PIPE
    popen = subprocess.Popen(args, stdout=stdout, stdin=stdin, cwd=cwd)

    output = popen.communicate()[0]
    if isinstance(output, bytes):
        output = output.decode(errors='backslashreplace')

    if popen.returncode:
        if failmsg:
            msg = "Failed to " + failmsg
        else:
            msg = "Failed to run " + args[0]
        if fatal:
            die(msg, details=output)
        else:
            warn(msg, details=output)
    return output if stdout == subprocess.PIPE else ''