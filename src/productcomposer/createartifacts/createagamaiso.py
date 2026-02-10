import os
import shutil
import glob
from ..utils.loggerutils import (note, die)
from ..utils.runhelper import run_helper
from ..utils.cryptoutils import create_sha_for
from ..config import (verbose_level, ISO_PREPARER)

def create_agama_iso(outdir, isoconf, build_options, pool, workdir, application_id, arch):
    verbose = True if verbose_level > 0 else False
    base = isoconf['base']
    if verbose:
        note(f"Looking for baseiso-{base} rpm on {arch}")
    agama = pool.lookup_rpm(arch, f"baseiso-{base}")
    if not agama:
        die(f"Base iso in baseiso-{base} rpm was not found")
    baseisodir = f"{outdir}/baseiso"
    os.mkdir(baseisodir)
    args = ['unrpm', '-q', agama.location]
    run_helper(args, cwd=baseisodir, failmsg=f"extract {agama.location}", verbose=verbose)
    files = glob.glob(f"usr/libexec/base-isos/{base}*.iso", root_dir=baseisodir)
    if not files:
        die(f"Base iso {base} not found in {agama}")
    if len(files) > 1:
        die(f"Multiple base isos for {base} found in {agama}")
    agamaiso = f"{baseisodir}/{files[0]}"
    if verbose:
        note(f"Found base iso image {agamaiso}")

    # create new iso
    tempdir = f"{outdir}/mksusecd"
    os.mkdir(tempdir)
    if 'base_skip_packages' not in build_options:
        args = ['cp', '-al', workdir, f"{tempdir}/install"]
        run_helper(args, failmsg="add tree to agama image")
    args = ['mksusecd', agamaiso, tempdir, '--create', workdir + '.install.iso']
    # mksusecd would take the volume_id, publisher, application_id, preparer from the agama iso
    args += ['--preparer', ISO_PREPARER]
    if 'publisher' in isoconf and isoconf['publisher'] is not None:
        args += ['--vendor', isoconf['publisher']]
    if 'volume_id' in isoconf and isoconf['volume_id'] is not None:
        args += ['--volume', isoconf['volume_id']]
    args += ['--application', application_id]
    run_helper(args, failmsg="add tree to agama image", verbose=verbose)
    # mksusecd already did a tagmedia call with a sha256 digest
    # cleanup directories
    shutil.rmtree(tempdir)
    shutil.rmtree(baseisodir)
    # just for the bootable image, signature is not yet applied, so ignore that error
    # FIXME: fatal=False due to unknown reported El Torrito error on s390x atm.
    run_helper(['verifymedia', workdir + '.install.iso', '--ignore', 'ISO is signed'], fatal=False, failmsg="verify install.iso")
    # creating .sha256/.sha512 for iso file
    checksums = ['sha256']
    if isoconf['checksums']:
        checksums = isoconf['checksums']
    for checksum in checksums:
        create_sha_for(workdir + ".install.iso", checksum)
