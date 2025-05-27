from pathlib import Path

from .runhelper import run_helper


def create_sha256_for(filename: str) -> None:
    with open(f'{filename}.sha256', 'w') as sha_file:
        # argument must not have the path
        run_helper(
            ['sha256sum', Path(filename).name],
            cwd=Path(filename).parent.absolute(),
            stdout=sha_file,
            failmsg='create .sha256 file',
        )
