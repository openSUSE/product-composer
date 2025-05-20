import os
import subprocess
from ..wrappers import CreaterepoWrapper
from ..utils.loggerutils import (die, warn, note)

def run_createrepo(rpmdir, yml, content=[], repos=[]):
    product_type = '/o'
    if 'product-type' in yml:
        if yml['product-type'] == 'base':
            product_type = '/o'
        elif yml['product-type'] in ['module', 'extension']:
            product_type = '/a'
        else:
            die('Undefined product-type')
    cr = CreaterepoWrapper(directory=".")
    cr.distro = f"{yml.get('summary', yml['name'])} {yml['version']}"
    cr.cpeid = f"cpe:{product_type}:{yml['vendor']}:{yml['name']}:{yml['version']}"
    if 'update' in yml:
        cr.cpeid = cr.cpeid + f":{yml['update']}"
        if 'edition' in yml:
            cr.cpeid = cr.cpeid + f":{yml['edition']}"
    elif 'edition' in yml:
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
    if 'repodata' in yml:
        cr.complete_arch_list = yml['architectures']
        for arch in yml['architectures']:
            if os.path.isdir(f"{rpmdir}/{arch}"):
                cr.arch_specific_repodata = arch
                cr.run_cmd(cwd=rpmdir, stdout=subprocess.PIPE)