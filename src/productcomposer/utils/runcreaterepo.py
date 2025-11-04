import os
import subprocess
from ..wrappers import CreaterepoWrapper
from ..utils.loggerutils import die
from ..utils.cpeid import get_cpeid

def run_createrepo(rpmdir, yml, content=[], repos=[]):
    cr = CreaterepoWrapper(directory=".")
    cr.distro = f"{yml.get('summary', yml['name'])} {yml['version']}"
    cr.cpeid = get_cpeid(yml)
    cr.repos = repos
    # cr.split = True
    # cr.baseurl = "media://"
    cr.content = content
    cr.excludes = ["boot"]
    # default case including all architectures. Unique URL for all of them.
    # we need it in any case at least temporarly
    cr.run_cmd(cwd=rpmdir, stdout=subprocess.PIPE)
    # multiple arch specific meta data set
    if yml['repodata']:
        cr.complete_arch_list = yml['architectures']
        for arch in yml['architectures']:
            if os.path.isdir(f"{rpmdir}/{arch}"):
                cr.arch_specific_repodata = arch
                cr.run_cmd(cwd=rpmdir, stdout=subprocess.PIPE)
