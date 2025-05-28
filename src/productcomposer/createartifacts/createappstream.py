import os

OPENSUSE_APPSTREAM_PROCESS = '/usr/bin/openSUSE-appstream-process'

# Create the main susedata.xml with translations, support, and disk usage information
def create_appstream(rpmdir)
    if not os.path.exists(OPENSUSE_APPSTREAM_PROCESS):
        return

    args = [OPENSUSE_APPSTREAM_PROCESS, rpmdir, f"rpmdir/{repodata}" ]
    run_helper(args, failmsg="adding AppStream meta data", verbose=verbose)

