import os
from ..utils.runhelper import run_helper
from ..config import chksums_tool

def create_checksums_file(maindir):
    # Legacy linuxrc expect SHA 256 checksums, so don't follow global default here
    toolcmd = 'sha256sum'

    with open(maindir + '/CHECKSUMS', 'a') as chksums_file:
        for subdir in ('boot', 'EFI', 'docu', 'media.1'):
            if not os.path.exists(maindir + '/' + subdir):
                continue
            for root, dirnames, filenames in os.walk(maindir + '/' + subdir):
                for name in filenames:
                    relname = os.path.relpath(root + '/' + name, maindir)
                    run_helper(
                        [toolcmd, relname], cwd=maindir, stdout=chksums_file
                    )
