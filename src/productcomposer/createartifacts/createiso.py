import os
import shutil
from ..utils.loggerutils import (note,die)
from ..utils.runhelper import run_helper
from ..config import (verbose_level, ISO_PREPARER)
from ..utils.cryptoutils import create_sha256_for

def create_iso(outdir, yml, pool, flavor, workdir, application_id):
    verbose = True if verbose_level > 0 else False
    isoconf = yml['iso']
    args = ['/usr/bin/mkisofs', '-quiet', '-p', ISO_PREPARER]
    args += ['-r', '-pad', '-f', '-J', '-joliet-long']
    if 'publisher' in isoconf and isoconf['publisher'] is not None:
        args += ['-publisher', isoconf['publisher']]
    if 'volume_id' in isoconf and isoconf['volume_id'] is not None:
        args += ['-V', isoconf['volume_id']]
    args += ['-A', application_id]
    args += ['-o', workdir + '.iso', workdir]
    run_helper(args, cwd=outdir, failmsg="create iso file", verbose=verbose)
    # simple tag media call ... we may add options for pading or triggering media check later
    args = [ 'tagmedia' , '--digest' , 'sha256', workdir + '.iso' ]
    run_helper(args, cwd=outdir, failmsg="tagmedia iso file", verbose=verbose)
    # creating .sha256 for iso file
    create_sha256_for(workdir + ".iso")