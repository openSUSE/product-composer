import os

from ..config import verbose_level
from ..utils.runhelper import run_helper

OPENSUSE_APPSTREAM_PROCESS = '/usr/bin/openSUSE-appstream-process'


# Create the main susedata.xml with translations, support, and disk usage information
def create_appstream(rpmdir):
    if not os.path.exists(OPENSUSE_APPSTREAM_PROCESS):
        return

    run_helper(
        [OPENSUSE_APPSTREAM_PROCESS, rpmdir, f'{rpmdir}/repodata'],
        failmsg='adding AppStream meta data',
        verbose=verbose_level > 0,
    )
