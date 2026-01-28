from pathlib import Path

from .runhelper import run_helper

from .. import defaults
from ..utils.loggerutils import die, note, warn

def create_sha_for(filename: str) -> None:
    if defaults.ISO_CHECKSUM_TYPE == "sha256":
        suffix = '.sha256'
        tool = 'sha256sum'
    elif defaults.ISO_CHECKSUM_TYPE == "sha512":
        suffix = '.sha512'
        tool = 'sha512sum'
    else:
        die(f'Unkown checksum type: {defaults.ISO_CHECKSUM_TYPE}')

    with open(f'{filename}{suffix}', 'w') as sha_file:
        # argument must not have the path
        run_helper(
            [tool, Path(filename).name],
            cwd=Path(filename).parent.absolute(),
            stdout=sha_file,
            failmsg="create f{suffix} file",
        )
