import os
import re
from datetime import datetime
from xml.etree import ElementTree as ET
from ..utils.rpmutils import create_package_set
from ..utils.loggerutils import (note,warn,die)
from ..core.PkgSet import PkgSet
from ..core.Package import Package
from ..wrappers import ModifyrepoWrapper
from ..config import ET_ENCODING

# create a fake package entry from an updateinfo package spec
def create_updateinfo_package(pkgentry):
    entry = Package()
    for tag in ('name', 'epoch', 'version', 'release', 'arch'):
        setattr(entry, tag, pkgentry.get(tag))
    return entry

# Add updateinfo.xml to metadata
def create_updateinfo_xml(rpmdir, yml, pool, flavor, debugdir, sourcedir):
    if not pool.updateinfos:
        return

    missing_package = False

    # build the union of the package sets for all requested architectures

    ### This needs to be kept in sync with src/productcomposer/utils/rpmutils.py
    ### or factored out
    main_pkgset = PkgSet(None)
    for pkgset_name in yml['content']:
        for arch in yml['architectures']:
            main_pkgset.add(create_package_set(yml, arch, flavor, pkgset_name, pool=pool))

    main_pkgset_names = main_pkgset.names()
    ###

    uitemp = None

    for u in sorted(pool.lookup_all_updateinfos()):
        note("Add updateinfo " + u.location)
        for update in u.root.findall('update'):
            needed = False
            parent = update.findall('pkglist')[0].findall('collection')[0]

            # drop OBS internal patchinforef element
            for pr in update.findall('patchinforef'):
                update.remove(pr)

            if 'set_updateinfo_from' in yml:
                update.set('from', yml['set_updateinfo_from'])

            id_node = update.find('id')
            if 'set_updateinfo_id_prefix' in yml:
                # avoid double application of same prefix
                id_text = re.sub(r'^'+yml['set_updateinfo_id_prefix'], '', id_node.text)
                id_node.text = yml['set_updateinfo_id_prefix'] + id_text

            for pkgentry in parent.findall('package'):
                src = pkgentry.get('src')

                # check for embargo date
                embargo = pkgentry.get('embargo_date')
                if embargo is not None:
                    try:
                        embargo_time = datetime.strptime(embargo, '%Y-%m-%d %H:%M')
                    except ValueError:
                        embargo_time = datetime.strptime(embargo, '%Y-%m-%d')

                    if embargo_time > datetime.now():
                        warn(f"Update is still under embargo! {update.find('id').text}")
                        if 'block_updates_under_embargo' in yml['build_options']:
                            die("shutting down due to block_updates_under_embargo flag")

                # clean internal attributes
                for internal_attributes in (
                    'supportstatus',
                    'superseded_by',
                    'embargo_date',
                ):
                    pkgentry.attrib.pop(internal_attributes, None)

                # check if we have files for the entry
                if os.path.exists(rpmdir + '/' + src):
                    needed = True
                    continue
                if debugdir and os.path.exists(debugdir + '/' + src):
                    needed = True
                    continue
                if sourcedir and os.path.exists(sourcedir + '/' + src):
                    needed = True
                    continue
                name = pkgentry.get('name')
                pkgarch = pkgentry.get('arch')

                # do not insist on debuginfo or source packages
                if pkgarch == 'src' or pkgarch == 'nosrc':
                    parent.remove(pkgentry)
                    continue
                if name.endswith('-debuginfo') or name.endswith('-debugsource'):
                    parent.remove(pkgentry)
                    continue
                # ignore unwanted architectures
                if pkgarch != 'noarch' and pkgarch not in yml['architectures']:
                    parent.remove(pkgentry)
                    continue

                # check if we should have this package
                if name in main_pkgset_names:
                    updatepkg = create_updateinfo_package(pkgentry)
                    if main_pkgset.matchespkg(None, updatepkg):
                        warn(f"package {updatepkg} not found")
                        missing_package = True

                parent.remove(pkgentry)

            if not needed:
                if 'abort_on_empty_updateinfo' in yml['build_options']:
                    die(f'Stumbled over an updateinfo.xml where no rpm is used: {id_node.text}')
                continue

            if not uitemp:
                uitemp = open(rpmdir + '/updateinfo.xml', 'x')
                uitemp.write("<updates>\n  ")
            uitemp.write(ET.tostring(update, encoding=ET_ENCODING))

    if uitemp:
        uitemp.write("</updates>\n")
        uitemp.close()

        mr = ModifyrepoWrapper(
                file=os.path.join(rpmdir, "updateinfo.xml"),
                directory=os.path.join(rpmdir, "repodata"),
                )
        mr.run_cmd()

        os.unlink(rpmdir + '/updateinfo.xml')

    if missing_package and 'ignore_missing_packages' not in yml['build_options']:
        die('Abort due to missing packages for updateinfo')
