import os
import subprocess
from ..wrappers import CreaterepoWrapper
from ..utils.loggerutils import die

def run_createrepo(rpmdir, yml, content=[], repos=[]):
    match yml['product_type']:
        case 'base' | None:
            product_type = '/o'
        case 'module' | 'extension':
            product_type = '/a'
        case _:
            die('Undefined product-type')
    cr = CreaterepoWrapper(directory=".")
    cr.distro = f"{yml.get('summary', yml['name'])} {yml['version']}"
    if 'cpe' in yml and yml['cpe']:
        cr.cpeid = yml['cpe']
    else:
        cr.cpeid = f"cpe:{product_type}:{yml['vendor']}:{yml['name']}:{yml['version']}"
        if yml.get('update'):
            cr.cpeid = cr.cpeid + f":{yml['update']}"
            if yml.get('edition'):
                cr.cpeid = cr.cpeid + f":{yml['edition']}"
        elif yml.get('edition'):
            cr.cpeid = cr.cpeid + f"::{yml['edition']}"
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
