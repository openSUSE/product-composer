import os

from ..config import verbose_level
from ..utils.runhelper import run_helper
from ..wrappers import ModifyrepoWrapper

OPENSUSE_APPSTREAM_PROCESS = '/usr/bin/openSUSE-appstream-process'


# Create the additional app stream files if content provides necessary meta data
def create_appstream(rpmdir):
    if not os.path.exists(OPENSUSE_APPSTREAM_PROCESS):
        return

    run_helper(
        [OPENSUSE_APPSTREAM_PROCESS, rpmdir, f'{rpmdir}'],
        failmsg='Creating AppStream meta data',
        verbose=verbose_level > 0,
    )

    # Did the process create files?
    main_file = f'{rpmdir}/appdata.xml.gz'
    if not os.path.exists(main_file):
       return

    mr = ModifyrepoWrapper(
        file=main_file,
        mdtype='appdata',
        directory=os.path.join(rpmdir, "repodata"),
    )
    mr.run_cmd()
    os.unlink(main_file)

    icon_file = f'{rpmdir}/appdata-icons.tar.gz'
    if os.path.exists(icon_file):
        mr = ModifyrepoWrapper(
            file=icon_file,
            mdtype='appdata-icons',
            directory=os.path.join(rpmdir, "repodata"),
        )
        mr.run_cmd()
        os.unlink(icon_file)

    ignore_file = f'{rpmdir}/appdata-ignore.xml.gz'
    if os.path.exists(ignore_file):
        os.unlink(ignore_file)
