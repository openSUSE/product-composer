from pathlib import Path

from .runhelper import run_helper

from .. import defaults
from ..utils.loggerutils import die

def create_sha_for(filename: str, checksum_type: str = defaults.ISO_CHECKSUM_TYPE) -> None:

    if checksum_type == "sha256":
        suffix = '.sha256'
        tool = 'sha256sum'
    elif checksum_type == "sha512":
        suffix = '.sha512'
        tool = 'sha512sum'
    else:
        die(f'Unkown checksum type: {checksum_type}')

    with open(f'{filename}{suffix}', 'w') as sha_file:
        # argument must not have the path
        run_helper(
            [tool, Path(filename).name],
            cwd=Path(filename).parent.absolute(),
            stdout=sha_file,
            failmsg=f'create .{suffix} file'
        )
